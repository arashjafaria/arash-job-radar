"""Final checks shared by every Telegram entry point."""
from description_policy import description_block_reason, fpga_block_reason
from job_matcher import location_status
from title_policy import excluded_title_reason


def delivery_block_reason(job):
    reason = excluded_title_reason(job.get('title'))
    if reason:
        return reason
    evidence = job.get('_decision_evidence') or job.get('decision_evidence') or {}
    description = job.get('description') or job.get('description_text') or evidence.get('description', '')
    reason = fpga_block_reason(job.get("description"), job.get("description_text"),
                               evidence.get("description"))
    reason = reason or description_block_reason(
        description, job.get("requirements") or evidence.get("requirements"),
        job.get("tasks") or evidence.get("tasks"))
    if reason:
        return reason
    allowed, reason = location_status(job.get('location', ''), description)
    if allowed is not True:
        return reason
    return None
