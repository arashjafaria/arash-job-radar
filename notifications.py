"""A permanent database reservation precedes every job notification.

Telegram has no idempotency key. Prefer a missed/uncertain notification to a
duplicate: never release reservations or retry a Telegram request.
"""
import uuid

from supabase_store import save_job, update_job, claim_notification, finish_notification


def compact_message(message, url=""):
    """One vacancy is one Telegram message, including a usable vacancy link."""
    limit = 3900
    if len(message) <= limit:
        return message
    suffix = "\n…\n" + url[:500]
    return message[:limit - len(suffix)] + suffix


def notify_job_once(job, message, sender):
    source, job_id = job["source"], str(job["job_id"])
    save_job(source, job_id, title=job.get("title", ""),
             company=job.get("company", ""), location=job.get("location", ""),
             url=job.get("url", ""), status="notification_pending")
    update_job(source, job_id, **{key: job[key] for key in
               ("title", "company", "location", "url") if job.get(key)})
    token = str(uuid.uuid4())
    if not claim_notification(source, job_id, token):
        print("Notification suppressed by permanent history:", source, job_id)
        return False
    delivered = False
    try:
        delivered = bool(sender(compact_message(message, job.get("url", ""))))
        return delivered
    finally:
        # A failed finish cannot cause a second post: the claim already exists.
        finish_notification(source, job_id, token, delivered)


def was_notified(record):
    status = (record or {}).get("status", "") or ""
    return bool((record or {}).get("sent_to_telegram") or status == "sent"
                or status.startswith("review_digest_sent")
                or (record or {}).get("notification_status") in
                {"claimed", "delivered", "uncertain", "suppressed"})
