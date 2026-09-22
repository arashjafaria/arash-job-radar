import json
import os
import subprocess
import sys

import requests

from config import (
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)

from supabase_store import (
    job_exists,
    save_job,
)


SOURCE = "bmw"
SEEN_FILE = "bmw_seen_jobs.json"
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

def get_supabase_bmw_ids():

    all_ids = []

    offset = 0
    batch_size = 1000

    while True:

        response = requests.get(
            API_URL,
            headers=HEADERS,
            params={
                "select": "job_id",
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

        for row in rows:

            job_id = str(
                row.get(
                    "job_id",
                    ""
                )
            ).strip()

            if job_id:

                all_ids.append(
                    job_id
                )

        if len(rows) < batch_size:

            break

        offset += batch_size

    return set(
        all_ids
    )


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
):

    new_ids = (
        after_ids
        - before_ids
    )

    print()
    print(
        "New BMW IDs created by monitor:",
        len(new_ids)
    )

    inserted = 0
    failed = 0

    for job_id in new_ids:

        try:

            if job_exists(
                SOURCE,
                job_id
            ):

                continue

            saved = save_job(
                source=SOURCE,
                job_id=job_id,
                title="",
                company="BMW Group",
                location="",
                url=(
                    job_id
                    if job_id.startswith("http")
                    else ""
                ),
                posted_at="",
                match_score=None,
                status="seen_by_bmw_monitor",
                sent_to_telegram=False,
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

    supabase_ids = (
        get_supabase_bmw_ids()
    )

    print(
        "BMW jobs in Supabase:",
        len(supabase_ids)
    )


    # --------------------------------------------------------
    # 2. Preserve anything already local
    # --------------------------------------------------------

    local_ids = (
        get_local_ids()
    )

    print(
        "BMW jobs in local memory:",
        len(local_ids)
    )


    combined_ids = (
        supabase_ids
        | local_ids
    )


    print(
        "Combined BMW memory:",
        len(combined_ids)
    )


    # --------------------------------------------------------
    # 3. Give BMW monitor the complete memory
    # --------------------------------------------------------

    write_seen_file(
        combined_ids
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

    inserted, failed = (
        sync_to_supabase(
            supabase_ids,
            after_ids,
        )
    )


    print()
    print("=" * 70)
    print("BMW + SUPABASE SUMMARY")
    print("=" * 70)

    print(
        "Supabase before run:",
        len(supabase_ids)
    )

    print(
        "Local after BMW run:",
        len(after_ids)
    )

    print(
        "New jobs saved to Supabase:",
        inserted
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