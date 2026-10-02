import json
import os
import subprocess
import sys

import requests

from profile import MATCHER_REVISION

from config import (
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)

from supabase_store import (
    job_exists,
    save_job,
    update_job,
)


SOURCE = "bmw"
SEEN_FILE = "bmw_seen_jobs.json"
SENT_FILE = "bmw_sent_jobs.json"
REVIEW_FILE = "bmw_review_jobs.json"
BMW_MATCHER_REVISION = MATCHER_REVISION
TABLE = "arash_jobs"

API_URL = (
    f"{SUPABASE_URL}/rest/v1/{TABLE}"
)

HEADERS = {
    "apikey": SUPABASE_SECRET_KEY,
    "Content-Type": "application/json",
}


# ============================================================
# LOAD BMW MEMORY FROM SUPABASE
# ============================================================

def get_supabase_bmw_records():

    all_rows = []

    offset = 0
    batch_size = 1000

    while True:

        response = requests.get(
            API_URL,
            headers=HEADERS,
            params={
                "select": "job_id,status,sent_to_telegram",
                "source": "eq.bmw",
                "limit": str(batch_size),
                "offset": str(offset),
            },
            timeout=30,
        )

        if response.status_code != 200:

            raise RuntimeError(
                "Could not read BMW memory from Supabase: "
                + response.text
            )

        rows = response.json()
        all_rows.extend(
            rows
        )

        if len(rows) < batch_size:
            break

        offset += batch_size

    return all_rows


def get_current_seen_ids(
    records,
):
    current_tag = (
        "@"
        + BMW_MATCHER_REVISION
    )

    result = set()

    for row in records:
        job_id = str(
            row.get(
                "job_id",
                ""
            )
        ).strip()

        if not job_id:
            continue

        status = (
            row.get(
                "status",
                ""
            )
            or ""
        )

        if (
            row.get(
                "sent_to_telegram"
            )
            or status == "sent"
            or status.endswith(
                current_tag
            )
        ):
            result.add(
                job_id
            )

    return result


# ============================================================
# LOAD LOCAL MEMORY
# ============================================================

def get_local_ids():

    if not os.path.exists(
        SEEN_FILE
    ):

        return set()

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if isinstance(
            data,
            list
        ):

            return set(
                str(item).strip()
                for item in data
                if str(item).strip()
            )

        if isinstance(
            data,
            dict
        ):

            return set(
                str(item).strip()
                for item in data.keys()
                if str(item).strip()
            )

    except Exception as exc:

        print(
            "Local BMW memory read error:",
            exc
        )

    return set()


def get_sent_ids():

    if not os.path.exists(
        SENT_FILE
    ):
        return set()

    try:
        with open(
            SENT_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

        if isinstance(
            data,
            list
        ):
            return set(
                str(item).strip()
                for item in data
                if str(item).strip()
            )

    except Exception as exc:
        print(
            "BMW sent-file read error:",
            exc
        )

    return set()


def get_review_jobs():
    """Read the BMW monitor's per-run review candidates before syncing."""
    if not os.path.exists(REVIEW_FILE):
        return {}
    with open(REVIEW_FILE, "r", encoding="utf-8") as file:
        rows = json.load(file)
    if not isinstance(rows, list):
        raise ValueError("BMW review output must be a list")
    return {
        str(row["job_id"]): row
        for row in rows
        if isinstance(row, dict) and row.get("job_id")
    }


# ============================================================
# WRITE MEMORY FOR BMW MONITOR
# ============================================================

def write_seen_file(
    job_ids
):

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            sorted(
                list(job_ids)
            ),
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# SYNC NEW BMW JOBS TO SUPABASE
# ============================================================

def sync_to_supabase(
    before_ids,
    after_ids,
    sent_ids,
    review_jobs=None,
):

    processed_ids = (
        after_ids
        - before_ids
    )
    review_jobs = review_jobs or {}

    print()
    print(
        "BMW IDs processed by monitor:",
        len(processed_ids)
    )

    inserted = 0
    updated = 0
    failed = 0

    revision_status = (
        "seen_by_bmw_monitor@"
        + BMW_MATCHER_REVISION
    )

    for job_id in processed_ids:

        try:

            sent = (
                job_id
                in sent_ids
            )

            review = review_jobs.get(job_id)
            status = (
                "sent" if sent else (
                    "review_required@" + BMW_MATCHER_REVISION
                    if review else revision_status
                )
            )

            if job_exists(
                SOURCE,
                job_id
            ):
                update_job(
                    SOURCE,
                    job_id,
                    status=status,
                    sent_to_telegram=sent,
                    match_score=review.get("score") if review else None,
                    posted_at=review.get("posted_at") if review else None,
                    title=review.get("title") if review else None,
                    company=review.get("company") if review else None,
                    location=review.get("location") if review else None,
                    url=review.get("url") if review else None,
                )
                updated += 1
                continue

            saved = save_job(
                source=SOURCE,
                job_id=job_id,
                title=review.get("title", "") if review else "",
                company="BMW Group",
                location=review.get("location", "") if review else "",
                url=review.get("url", "") if review else (
                    job_id if job_id.startswith("http") else ""
                ),
                posted_at=review.get("posted_at", "") if review else "",
                match_score=review.get("score") if review else None,
                status=status,
                sent_to_telegram=sent,
            )

            if saved:
                inserted += 1

        except Exception as exc:

            print(
                "Supabase sync error:",
                job_id,
                exc
            )

            failed += 1

    return (
        inserted,
        updated,
        failed
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("BMW RADAR - SUPABASE BRIDGE")
    print("=" * 70)

    if not SUPABASE_URL:

        raise SystemExit(
            "SUPABASE_URL missing."
        )

    if not SUPABASE_SECRET_KEY:

        raise SystemExit(
            "SUPABASE_SECRET_KEY missing."
        )


    # --------------------------------------------------------
    # 1. Read Supabase memory
    # --------------------------------------------------------

    supabase_records = (
        get_supabase_bmw_records()
    )

    all_supabase_ids = set(
        str(
            row.get(
                "job_id",
                ""
            )
        ).strip()
        for row in supabase_records
        if str(
            row.get(
                "job_id",
                ""
            )
        ).strip()
    )

    current_seen_ids = (
        get_current_seen_ids(
            supabase_records
        )
    )

    print(
        "BMW jobs in Supabase:",
        len(all_supabase_ids)
    )

    print(
        "BMW jobs valid for current matcher revision:",
        len(current_seen_ids)
    )

    print(
        "BMW legacy/stale jobs eligible for one-time recheck:",
        len(
            all_supabase_ids
            - current_seen_ids
        )
    )


    # --------------------------------------------------------
    # 2. Give BMW monitor only current-revision memory
    # --------------------------------------------------------

    write_seen_file(
        current_seen_ids
    )


    print()
    print(
        "Starting bmw_monitor.py..."
    )
    print()


    # --------------------------------------------------------
    # 4. Run existing BMW monitor
    # --------------------------------------------------------

    result = subprocess.run(
        [
            sys.executable,
            "bmw_monitor.py",
        ]
    )


    if result.returncode != 0:

        raise SystemExit(
            "BMW monitor failed. "
            f"Exit code: {result.returncode}"
        )


    # --------------------------------------------------------
    # 5. Read updated BMW memory
    # --------------------------------------------------------

    after_ids = (
        get_local_ids()
    )


    # --------------------------------------------------------
    # 6. Sync new IDs to Supabase
    # --------------------------------------------------------

    sent_ids = (
        get_sent_ids()
    )
    review_jobs = get_review_jobs()

    inserted, updated, failed = (
        sync_to_supabase(
            current_seen_ids,
            after_ids,
            sent_ids,
            review_jobs,
        )
    )


    print()
    print("=" * 70)
    print("BMW + SUPABASE SUMMARY")
    print("=" * 70)

    print(
        "Supabase before run:",
        len(all_supabase_ids)
    )

    print(
        "Local after BMW run:",
        len(after_ids)
    )

    print(
        "New BMW rows saved to Supabase:",
        inserted
    )

    print(
        "Existing BMW rows updated:",
        updated
    )

    print(
        "Supabase sync failures:",
        failed
    )

    print("=" * 70)

    if failed == 0:

        print(
            "BMW SUPABASE BRIDGE: SUCCESS"
        )

    else:

        print(
            "BMW SUPABASE BRIDGE: "
            "COMPLETED WITH ERRORS"
        )

    print("=" * 70)


if __name__ == "__main__":

    main()