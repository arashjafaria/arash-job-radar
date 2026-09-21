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


def _check_config():

    if not SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is missing."
        )

    if not SUPABASE_SECRET_KEY:
        raise RuntimeError(
            "SUPABASE_SECRET_KEY is missing."
        )


# ============================================================
# CHECK IF JOB WAS ALREADY SEEN
# ============================================================

def job_exists(
    source,
    job_id
):

    _check_config()

    response = requests.get(
        API_URL,
        headers=HEADERS,
        params={
            "select": "id",
            "source": f"eq.{source}",
            "job_id": f"eq.{job_id}",
            "limit": "1",
        },
        timeout=20,
    )


    if response.status_code != 200:

        raise RuntimeError(
            "Supabase job_exists failed: "
            + response.text
        )


    rows = response.json()

    return bool(rows)


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


    response = requests.post(
        API_URL,
        headers=headers,
        json=data,
        timeout=20,
    )


    # 201 = inserted
    if response.status_code == 201:

        return True


    # Duplicate job.
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


    if not data:

        return True


    response = requests.patch(
        API_URL,
        headers=HEADERS,
        params={
            "source": f"eq.{source}",
            "job_id": f"eq.{job_id}",
        },
        json=data,
        timeout=20,
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


    response = requests.get(
        API_URL,
        headers=headers,
        params=params,
        timeout=20,
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