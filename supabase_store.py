import time
import re
from difflib import SequenceMatcher

import requests

from config import (
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


TABLE = "arash_jobs"

API_URL = (
    f"{SUPABASE_URL}/rest/v1/{TABLE}"
)


HEADERS = {
    "apikey": SUPABASE_SECRET_KEY,
    "Content-Type": "application/json",
}


RETRYABLE_STATUS = {
    429,
    500,
    502,
    503,
    504,
}

MAX_ATTEMPTS = 3


def _check_config():

    if not SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is missing."
        )

    if not SUPABASE_SECRET_KEY:
        raise RuntimeError(
            "SUPABASE_SECRET_KEY is missing."
        )


def _request(
    method,
    *,
    headers=None,
    params=None,
    json=None,
    timeout=20,
):

    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1
    ):

        try:

            response = requests.request(
                method,
                API_URL,
                headers=headers or HEADERS,
                params=params,
                json=json,
                timeout=timeout,
            )

            if (
                response.status_code
                not in RETRYABLE_STATUS
            ):
                return response

            last_error = RuntimeError(
                "Supabase temporary HTTP "
                f"{response.status_code}: "
                f"{response.text[:300]}"
            )

        except requests.RequestException as exc:

            last_error = exc


        if attempt < MAX_ATTEMPTS:

            wait_seconds = (
                2 ** attempt
            )

            print(
                "Supabase temporary failure. "
                f"Retry {attempt + 1}/{MAX_ATTEMPTS} "
                f"in {wait_seconds}s..."
            )

            time.sleep(
                wait_seconds
            )


    raise RuntimeError(
        "Supabase request failed after "
        f"{MAX_ATTEMPTS} attempts: "
        f"{last_error}"
    )


# ============================================================
# CHECK IF JOB WAS ALREADY SEEN
# ============================================================

def job_exists(
    source,
    job_id
):

    _check_config()

    response = _request(
        "GET",
        params={
            "select": "id",
            "source": f"eq.{source}",
            "job_id": f"eq.{job_id}",
            "limit": "1",
        },
    )


    if response.status_code != 200:

        raise RuntimeError(
            "Supabase job_exists failed: "
            + response.text
        )


    rows = response.json()

    return bool(rows)


def get_job_record(
    source,
    job_id,
):
    _check_config()

    response = _request(
        "GET",
        params={
            "select": "id,status,sent_to_telegram,posted_at,match_score",
            "source": f"eq.{source}",
            "job_id": f"eq.{job_id}",
            "limit": "1",
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Supabase get_job_record failed: "
            + response.text
        )

    rows = response.json()

    if not rows:
        return None

    return rows[0]


# ============================================================
# SAVE NEW JOB
# ============================================================

def save_job(
    source,
    job_id,
    title="",
    company="",
    location="",
    url="",
    posted_at="",
    match_score=None,
    status="seen",
    sent_to_telegram=False,
):

    _check_config()


    data = {
        "source": source,
        "job_id": str(job_id),
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "posted_at": posted_at or None,
        "match_score": match_score,
        "status": status,
        "sent_to_telegram": sent_to_telegram,
    }


    headers = {
        **HEADERS,
        "Prefer": "return=minimal",
    }


    response = _request(
        "POST",
        headers=headers,
        json=data,
    )


    # 201 = inserted
    if response.status_code == 201:

        return True


    # Duplicate job.
    # This can also happen when the first POST succeeded
    # but its response timed out and the retry repeats it.
    if response.status_code == 409:

        return False


    raise RuntimeError(
        "Supabase save_job failed: "
        + response.text
    )


# ============================================================
# UPDATE EXISTING JOB
# ============================================================

def update_job(
    source,
    job_id,
    match_score=None,
    status=None,
    sent_to_telegram=None,
    posted_at=None,
):

    _check_config()


    data = {}


    if match_score is not None:

        data["match_score"] = (
            match_score
        )


    if status is not None:

        data["status"] = (
            status
        )


    if sent_to_telegram is not None:

        data[
            "sent_to_telegram"
        ] = sent_to_telegram

    if posted_at is not None:

        data[
            "posted_at"
        ] = posted_at or None


    if not data:

        return True


    response = _request(
        "PATCH",
        params={
            "source": f"eq.{source}",
            "job_id": f"eq.{job_id}",
        },
        json=data,
    )


    if response.status_code not in (
        200,
        204,
    ):

        raise RuntimeError(
            "Supabase update_job failed: "
            + response.text
        )


    return True



# ============================================================
# CROSS-SOURCE DUPLICATE CHECK
# ============================================================

def _normalize_title(value):
    text = (value or "").lower()
    text = re.sub(
        r"\((?:m|w|d|f|x|all|gender|genders|div|gn)[^)]*\)",
        " ",
        text,
    )
    text = re.sub(
        r"\b(?:all genders?|mwd|m/w/d|w/m/d|d/m/w|f/m/d)\b",
        " ",
        text,
    )
    text = text.replace("entwicklungsingenieur", "development engineer")
    text = text.replace("testingenieur", "test engineer")
    text = text.replace("systemingenieur", "system engineer")
    text = text.replace("validierungsingenieur", "validation engineer")
    text = re.sub(r"[^a-z0-9äöüß+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_company(value):
    text = (value or "").lower()
    text = re.sub(
        r"\b(?:gmbh|ag|se|kg|co|ltd|limited|inc|corp|corporation)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9äöüß]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_location(value):
    text = (value or "").lower()
    text = text.replace("münchen", "munich")
    text = text.replace("nürnberg", "nuremberg")
    text = re.sub(r"[^a-z0-9äöüß]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_sent_duplicate(
    source,
    title,
    company,
    location="",
):
    """
    Find an already-sent job from another source with essentially the
    same company/title/location. This prevents LinkedIn, Indeed and
    StepStone from sending the same vacancy multiple times.
    """
    _check_config()

    response = _request(
        "GET",
        params={
            "select": "source,job_id,title,company,location,url",
            "sent_to_telegram": "eq.true",
            "order": "id.desc",
            "limit": "500",
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Supabase duplicate lookup failed: "
            + response.text
        )

    target_title = _normalize_title(
        title
    )
    target_company = _normalize_company(
        company
    )
    target_location = _normalize_location(
        location
    )

    if (
        not target_title
        or not target_company
    ):
        return None

    for row in response.json():
        if (
            row.get(
                "source"
            )
            == source
        ):
            continue

        other_title = _normalize_title(
            row.get(
                "title",
                ""
            )
        )
        other_company = _normalize_company(
            row.get(
                "company",
                ""
            )
        )

        if (
            not other_title
            or not other_company
        ):
            continue

        company_ratio = SequenceMatcher(
            None,
            target_company,
            other_company,
        ).ratio()

        if company_ratio < 0.90:
            continue

        title_ratio = SequenceMatcher(
            None,
            target_title,
            other_title,
        ).ratio()

        if title_ratio < 0.90:
            continue

        other_location = _normalize_location(
            row.get(
                "location",
                ""
            )
        )

        if (
            target_location
            and other_location
            and "remote" not in target_location
            and "remote" not in other_location
        ):
            # Keep location comparison permissive because one source may
            # say "Munich" and another "Munich, Bavaria, Germany".
            if (
                target_location not in other_location
                and other_location not in target_location
            ):
                continue

        return row

    return None


# ============================================================
# COUNT JOBS
# ============================================================

def count_jobs(
    source=None
):

    _check_config()


    headers = {
        **HEADERS,
        "Prefer": "count=exact",
    }


    params = {
        "select": "id",
    }


    if source:

        params[
            "source"
        ] = f"eq.{source}"


    response = _request(
        "GET",
        headers=headers,
        params=params,
    )


    if response.status_code != 200:

        raise RuntimeError(
            "Supabase count_jobs failed: "
            + response.text
        )


    content_range = (
        response.headers.get(
            "Content-Range",
            ""
        )
    )


    if "/" not in content_range:

        return len(
            response.json()
        )


    total = (
        content_range
        .split("/")[-1]
    )


    try:

        return int(total)

    except Exception:

        return len(
            response.json()
        )
