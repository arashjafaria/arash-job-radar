"""Second-stage decisions, followed by at most one lifetime job notification."""
import os
import time

import requests

from profile import MATCHER_REVISION
from decisions import evaluate_details, record_decision
from notifications import notify_job_once
from supabase_store import _check_config, _request, update_job

MAX_PER_RUN = 25
NEW_JOB_SLOTS = 20
REVIEW_BUDGET_SECONDS = 300
DETAIL_DELAY_SECONDS = 2.5
TELEGRAM_SAFE_LENGTH = 3900


def pending_reviews():
    _check_config()
    def fetch(filters, order):
        response = _request("GET", params={
            "select": "*", **filters, "order": order,
            "limit": str(MAX_PER_RUN),
        })
        if response.status_code != 200:
            raise RuntimeError("Review queue request failed")
        return response.json()

    # Fresh opportunities must not sit behind already-delivered legacy digests.
    new_jobs = fetch({
        "status": "like.review_required*",
        "sent_to_telegram": "eq.false",
        "or": "(notification_status.is.null,notification_status.not.in.(claimed,delivered,uncertain,suppressed))",
    }, "first_seen_at.desc,id.desc")
    historical_jobs = fetch({
        "and": "(or(status.like.review_required*,status.like.review_digest_sent*),or(sent_to_telegram.eq.true,status.like.review_digest_sent*,notification_status.in.(claimed,delivered,uncertain,suppressed)))",
    }, "id.asc")
    historical_slots = MAX_PER_RUN - NEW_JOB_SLOTS
    candidates = (new_jobs[:NEW_JOB_SLOTS] + historical_jobs[:historical_slots]
                  + new_jobs[NEW_JOB_SLOTS:] + historical_jobs[historical_slots:])
    rows, seen = [], set()
    for row in candidates:
        key = (row["source"], str(row["job_id"]))
        if key not in seen:
            rows.append(row)
            seen.add(key)
        if len(rows) == MAX_PER_RUN:
            break
    return rows


def fresh_details(row):
    if row["source"] == "linkedin":
        from linkedin_monitor import get_job_details
        from public_sources_monitor import extract_sections
        details = get_job_details(row["job_id"])
        if details and details.get("description_html"):
            # Independent paragraph-aware extraction for the second pass.
            sections = extract_sections(details["description_html"])
            for key in ("requirements", "tasks"):
                if not details.get(key) and sections.get(key):
                    details[key] = sections[key]
        return details
    if row["source"] == "bmw":
        from bmw_monitor import get_job_details
        return get_job_details(row["url"])
    if row["source"] in {"stepstone", "indeed"}:
        from public_sources_monitor import get_details
        return get_details(row)
    return None


def review(row):
    try:
        details = fresh_details(row)
    except requests.RequestException:
        details = None
    if not details or not (details.get("description") or details.get("description_text")):
        return "manual", {"decision": "manual", "stage": "second_review",
                          "reason": "fresh job description unavailable; cannot verify requirements"}, None
    return evaluate_details(row, details)


def build_digest(rows):
    """Offline preview; delivery is reserved per individual job."""
    message, included = "Job Radar — reviewed opportunities\n", []
    for row in rows:
        chunk = "\n• " + str(row.get("title") or "Unknown role")[:100]
        chunk += "\n" + str(row.get("company") or "Unknown company")[:60]
        chunk += "\n" + str(row.get("url") or "")[:300] + "\n"
        if len(message + chunk) > TELEGRAM_SAFE_LENGTH:
            break
        message += chunk
        included.append(row)
    return message, included


def send_telegram(message):
    token, chat = os.getenv("BOT_TOKEN"), os.getenv("CHAT_ID")
    if not token or not chat:
        raise RuntimeError("Missing Telegram configuration for reviewed job")
    response = requests.post(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data={"chat_id": chat, "text": message, "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("ok") is True


def main():
    rows = pending_reviews()
    if not rows:
        print("Review queue empty; no Telegram digest needed.")
        return
    started = time.monotonic()
    processed = 0
    for index, row in enumerate(rows):
        if time.monotonic() - started >= REVIEW_BUDGET_SECONDS:
            print("Review time budget reached; remaining jobs stay queued for the next run.")
            break
        if index:
            time.sleep(DETAIL_DELAY_SECONDS)
        decision, evidence, score = review(row)
        record_decision(row["source"], row["job_id"], decision, score, evidence)
        processed += 1
        print("Second review:", row["source"], row["job_id"], decision, evidence["reason"])
        if decision == "reject":
            update_job(row["source"], row["job_id"], match_score=score,
                       status="rejected_review@" + MATCHER_REVISION)
            continue
        label = "✅ APPLY" if decision == "apply" else "⚠️ MANUAL REVIEW"
        message = label + (f" — {score}%" if score is not None else "")
        message += "\n" + str(row.get("title", "")) + "\n" + str(row.get("company", ""))
        message += "\n" + evidence["reason"] + "\n" + str(row.get("url", ""))
        notify_job_once(row, message, send_telegram)
        update_job(row["source"], row["job_id"], match_score=score,
                   status=("apply" if decision == "apply" else "manual_review") + "@" + MATCHER_REVISION)
    print(f"Review batch completed: {processed}/{len(rows)} jobs evaluated.")


if __name__ == "__main__":
    main()
