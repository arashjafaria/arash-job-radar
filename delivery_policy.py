"""Final checks shared by every Telegram entry point."""
from job_matcher import location_status
from title_policy import excluded_title_reason


def delivery_block_reason(job):
    reason = excluded_title_reason(job.get('title'))
    if reason:
        return reason
    evidence = job.get('_decision_evidence') or job.get('decision_evidence') or {}
    description = job.get('description') or job.get('description_text') or evidence.get('description', '')
    allowed, reason = location_status(job.get('location', ''), description)
    if allowed is not True:
        return reason
    return None
