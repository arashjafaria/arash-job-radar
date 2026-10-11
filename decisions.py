"""Traceable matching decisions; delivery is handled separately."""
from job_matcher import (
    evaluate_fit, location_status, contract_status, german_requirement,
    extract_candidate_experience_years, experience_status, is_senior_title,
)
from profile import MATCHER_REVISION, MIN_MATCH_PERCENT, SENIOR_MIN_MATCH_PERCENT, EXCLUDE_WORDS
from supabase_store import save_decision


def fit_decision(title, score, breakdown):
    if breakdown.get("review_required"):
        missing = []
        if not breakdown.get("requirements_evidence"):
            missing.append("no classified requirements")
        if not breakdown.get("core_evidence"):
            missing.append("no verified core evidence")
        if breakdown.get("low_evidence_coverage"):
            missing.append(f"evidence coverage {breakdown.get('evidence_coverage_percent', 0)}%")
        if breakdown.get("uncertain_requirements"):
            missing.append(f"{breakdown['uncertain_requirements']} unclassified requirements")
        return "manual", "; ".join(missing) or "insufficient verified requirement evidence"
    if not breakdown.get("gates_pass"):
        return "reject", "requirements/core/domain gates failed"
    if score < MIN_MATCH_PERCENT:
        return "reject", "overall score below threshold"
    if is_senior_title(title) and score < SENIOR_MIN_MATCH_PERCENT:
        return "reject", "senior role below required fit"
    return "apply", "verified requirement gates and score passed"


def record_decision(source, job_id, status, score=None, evidence=None):
    evidence = dict(evidence or {})
    if "decision" not in evidence:
        if status.startswith("review_required"):
            decision, reason = fit_decision(evidence.get("title", ""), score or 0,
                                            evidence.get("breakdown", {"review_required": True}))
        elif status == "sent" or status == "apply":
            decision, reason = "apply", "verified matching gates passed"
        else:
            decision, reason = "reject", status.split("@", 1)[0]
        evidence.update(decision=decision, reason=reason)
    evidence.update(matcher_revision=MATCHER_REVISION, score=score)
    save_decision(source, job_id, evidence["decision"], evidence)


def evaluate_details(row, details):
    """Second-stage re-evaluation applies the same hard filters and fit gates."""
    title = details.get("title") or row.get("title", "")
    description = details.get("description") or details.get("description_text", "")
    requirements, tasks = details.get("requirements", []), details.get("tasks", [])
    full_text = title + " " + description
    loc_ok, loc_reason = location_status(details.get("location") or row.get("location", ""), description)
    contract_reject, contract_reason = contract_status(
        details.get("criteria") or {"employment type": details.get("employment_type", "")}, description)
    years = extract_candidate_experience_years(requirements, description)
    exp_reject, exp_reason = experience_status(years)
    language_reject, language_reason, _ = german_requirement(full_text)
    checks = {"location": loc_reason, "contract": contract_reason,
              "experience": exp_reason, "language": language_reason}
    evidence = {"title": title, "description": description, "requirements": requirements,
                "tasks": tasks, "checks": checks, "stage": "second_review"}
    for rejected, reason in (
        (any(word in title.lower() for word in EXCLUDE_WORDS), "excluded title"),
        (not loc_ok, loc_reason), (contract_reject, contract_reason),
        (exp_reject, exp_reason), (language_reject, language_reason),
    ):
        if rejected:
            return "reject", {**evidence, "decision": "reject", "reason": reason}, None
    score, _, warnings, breakdown = evaluate_fit(title, description, requirements, tasks)
    decision, reason = fit_decision(title, score, breakdown)
    evidence.update(decision=decision, reason=reason, score=score,
                    breakdown=breakdown, warnings=warnings)
    return decision, evidence, score
