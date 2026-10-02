"""Low-confidence jobs: one small digest daily, without loss when StepStone is blocked."""
import os

import requests
from profile import MATCHER_REVISION
from supabase_store import _check_config, _request, update_job

MAX_PER_DIGEST = 8
TELEGRAM_SAFE_LENGTH = 3900


def pending_reviews():
    _check_config()
    response = _request(
        "GET",
        params={
            "select": "source,job_id,title,company,location,url,status",
            "status": "like.review_required@*",
            "order": "id.asc",
            "limit": str(MAX_PER_DIGEST),
        },
    )
    if response.status_code != 200:
        raise RuntimeError("Review queue request failed")
    return response.json()


def build_digest(rows):
    message = (
        "🔎 Job Radar — additional opportunities for manual review\n"
        "These were NOT verified as automatic matches. Review the actual requirements.\n"
    )
    included = []
    for row in rows:
        chunk = (
            "\n• " + str(row.get("title") or "Unknown role")[:100]
            + "\n" + str(row.get("company") or "Unknown company")[:60]
            + " | " + str(row.get("source") or "unknown")[:20]
            + "\n" + str(row.get("url") or "")[:300] + "\n"
        )
        if len(message + chunk) > TELEGRAM_SAFE_LENGTH:
            break
        message += chunk
        included.append(row)
    return message, included


def main():
    rows = pending_reviews()
    if not rows:
        print("Review queue empty; no Telegram digest needed.")
        return
    message, included = build_digest(rows)
    if not included:
        raise RuntimeError("Could not fit the first review item into Telegram.")
    token, chat = os.getenv("BOT_TOKEN"), os.getenv("CHAT_ID")
    if not token or not chat:
        raise SystemExit("Missing Telegram configuration for review digest")
    response = requests.post(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data={"chat_id": chat, "text": message, "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
    print("Manual-review digest delivered:", len(included))
    # Never mark a row as delivered unless it actually appeared in the message.
    for row in included:
        update_job(row["source"], row["job_id"], status="review_digest_sent@" + MATCHER_REVISION)


if __name__ == "__main__":
    main()
