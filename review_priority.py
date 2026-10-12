"""Cheap queue ordering from existing matcher evidence; never a hiring decision."""
from datetime import datetime, timezone


VERSION = 1


def percent(value):
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def build_priority(evidence):
    b = (evidence or {}).get("breakdown") or {}
    if not b or "evidence_coverage_percent" not in b:
        return {"version": VERSION, "base": 0, "known": False, "components": {}}
    coverage = percent(b.get("evidence_coverage_percent")) / 100
    tasks = b.get("responsibility_details") or []
    task_coverage = sum(float(item.get("weight", 0)) >= 2 for item in tasks) / len(tasks) if tasks else 0
    # A percentage based on a few recognised phrases must not dominate the queue.
    components = {
        "core_fit": round(25 * percent(b.get("core_requirements")) / 100 * coverage, 2)
                    if b.get("core_evidence") else 0,
        "task_fit": round(35 * percent(b.get("responsibilities")) / 100 * task_coverage, 2),
        "requirements_fit": round(15 * percent(b.get("requirements")) / 100 * coverage, 2),
        "confidence": round(10 * coverage, 2),
    }
    return {"version": VERSION, "base": round(sum(components.values()), 2),
            "known": True, "components": components}


def instant(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except (TypeError, ValueError):
        return None


def queue_priority(row, now=None):
    now = now or datetime.now(timezone.utc)
    saved = row.get("review_priority") or (row.get("decision_evidence") or {}).get("review_priority")
    saved = saved or build_priority(row.get("decision_evidence"))
    base = max(0, min(85, percent(saved.get("base"))))
    posted = instant(row.get("posted_at"))
    age = (now - posted).total_seconds() / 3600 if posted else None
    # Publication time is at most 15 points; unknown/future dates get no boost.
    fresh = (15 if age <= 24 else 10 if age <= 72 else 5 if age <= 168 else 0) \
            if age is not None and age >= 0 else 0
    seen = instant(row.get("first_seen_at"))
    waiting = max(0, (now - seen).total_seconds() / 3600) if seen else 0
    return round(base + fresh + min(10, waiting / 2), 2)


def prioritize(rows, now=None):
    now = now or datetime.now(timezone.utc)
    return sorted(rows, key=lambda row: queue_priority(row, now), reverse=True)
