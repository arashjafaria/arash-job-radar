"""Scheduled weekly summary: StepStone dry-run + previously queued low-confidence jobs."""
import json
import os
from pathlib import Path

import requests
from supabase_store import _request, _check_config, update_job

CURRENT_MATCHER_REVISION = "2026-10-02-a"
MAX_REVIEW_JOBS_PER_DIGEST = 8


def query_reviews():
    _check_config()
    response = _request(
        "GET",
        params={
            "select": "source,job_id,title,company,location,url,match_score,status",
            "status": "like.review_required@*",
            "order": "id.asc",
            "limit": str(MAX_REVIEW_JOBS_PER_DIGEST),
        },
    )
    if response.status_code != 200:
        raise RuntimeError("Unable to read weekly review queue from Supabase")
    return response.json()


def build_report(health, reviews):
    lines = [
        "📊 Arash Job Radar — weekly validation",
        "StepStone: DRY RUN ONLY, no test advertisements sent",
        "Advertisements found: " + str(health["candidates"]),
        "Advertisements assessed: " + str(health["checked"]),
        "Potential matches: " + str(health["potential_matches_not_sent"]) + " (not yet accuracy-certified)",
        "Indeed: inactive (access not validated)",
        "",
        "🔎 Low-confidence opportunities for manual review: " + str(len(reviews)),
    ]
    for row in reviews:
        lines.extend([
            "",
            "• " + str(row.get("title") or "Unknown title")[:100],
            str(row.get("company") or "Unknown employer")[:60]
            + " | " + str(row.get("source") or "unknown"),
            str(row.get("url") or "")[:280],
        ])
    return "\n".join(lines)[:3900]


def main():
    if os.getenv("MARKET_DRY_RUN") != "1":
        raise SystemExit("Weekly market summary requires MARKET_DRY_RUN=1")
    health = json.loads(Path("market_health.json").read_text(encoding="utf-8"))
    if not health.get("healthy"):
        raise SystemExit("Weekly validation did not pass")
    reviews = query_reviews()
    token, chat = os.getenv("BOT_TOKEN"), os.getenv("CHAT_ID")
    if not token or not chat:
        raise SystemExit("Missing Telegram configuration for weekly summary")
    response = requests.post(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data={"chat_id": chat, "text": build_report(health, reviews), "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
    print("Weekly validation summary delivered; reviews:", len(reviews))
    for row in reviews:
        update_job(
            row["source"], row["job_id"],
            status="review_digest_sent@" + CURRENT_MATCHER_REVISION,
        )


if __name__ == "__main__":
    main()
