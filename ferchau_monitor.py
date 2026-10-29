"""Separate FERCHAU Telegram collector; dry-run unless --post is supplied."""
import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from alten_monitor import clean, city, normalized_title, send_telegram
from config import SUPABASE_URL, SUPABASE_SECRET_KEY
from decisions import evaluate_details, record_decision
from delivery_policy import delivery_block_reason
from notifications import notify_job_once, was_notified
from profile import MATCHER_REVISION
from supabase_store import save_job
from title_policy import excluded_title_reason

BASE = "https://touch.ferchau.com"


def page_data(html):
    marker = "App.Data = "
    if marker not in html:
        raise ValueError("FERCHAU listing data missing")
    return json.JSONDecoder().raw_decode(html.split(marker, 1)[1])[0]["ControllerResponse"]


def reference(value):
    # LinkedIn references use LI, the same website vacancy uses FE.
    match = re.search(r"\b(?:FE|LI)(\d{2}-\d{5}-[A-Z0-9_-]+)\b", value or "", re.I)
    return match[1].upper() if match else ""


def candidate(item):
    if item.get("typeId") != 3 or item.get("locationCountryCode") != "DE":
        return None
    if item.get("jobTypeId") != 1:  # full-time employee vacancies only
        return None
    job_id = str(item["id"])
    slug = item.get("slug", "")
    if not job_id.isdigit() or not slug.startswith("/de/en/job/" + job_id + "/"):
        raise ValueError("Unexpected FERCHAU vacancy URL")
    def text(key):
        return clean(BeautifulSoup(item.get(key) or "", "html.parser").get_text(" ", strip=True))
    def bullets(key):
        return [clean(x.get_text(" ", strip=True)) for x in
                BeautifulSoup(item.get(key) or "", "html.parser").select("li")]
    return {"source": "ferchau", "job_id": job_id, "company": "FERCHAU",
        "title": clean(item["title"]), "url": urljoin(BASE, slug),
        "location": ", ".join(filter(None, [item.get("locationCity"),
            item.get("locationRegion"), "Germany"])),
        "requisition_id": item.get("number", ""), "employment_type": "Full-time",
        "tasks": bullets("tasks"), "requirements": bullets("requirements"),
        "description": "\n".join(text(k) for k in ("intro", "tasks", "requirements", "benefits", "outro"))}


def fetch_details(session, job):
    response = session.get(job["url"], timeout=25)
    response.raise_for_status()
    data = page_data(response.text)
    posting = None
    for head in data.get("Head", []):
        if head.get("attributes", {}).get("type") == "application/ld+json":
            schema = json.loads(head.get("content", "{}"))
            if schema.get("@type") == "JobPosting":
                posting = schema
    if posting is None or not posting.get("datePosted"):
        raise ValueError("Missing actual publication date; edit dates are not publication dates")
    offers = data["Data"]["Offers"]
    item = next((x for x in offers if str(x["id"]) == job["job_id"]), None)
    fresh = candidate(item) if item else None
    if not fresh or not fresh["tasks"] or not fresh["requirements"]:
        raise ValueError("Missing vacancy identity or task/requirement sections")
    return {**fresh, "posted_at": posting["datePosted"]}


def recent(job, now=None):
    try:
        posted = datetime.fromisoformat(job.get("posted_at", "").replace("Z", "+00:00"))
        posted = posted.replace(tzinfo=posted.tzinfo or timezone.utc)
        age = (now or datetime.now(timezone.utc)) - posted
        return timedelta(0) <= age <= timedelta(hours=24)
    except (ValueError, TypeError):
        return False


def assess(job):
    if not recent(job):
        return "reject", {"decision": "reject", "reason": "outside_24_hour_publication_window"}, None
    # Keep original requirements in the evidence. Optional clauses do not become
    # mandatory technical gaps (e.g. FERCHAU's MATLAB/Simulink advantage).
    required = []
    optional = re.compile(r"\b(ideally|advantage|preferred|desirable|optional|wünschenswert|idealerweise|von vorteil)\b", re.I)
    for line in job["requirements"]:
        for clause in line.split(";"):
            if not optional.search(clause):
                required.append(clause.strip())
    decision, evidence, score = evaluate_details(job, {**job, "requirements": required})
    evidence.update(requirements=job["requirements"], requisition_id=job["requisition_id"],
                    stage="ferchau_structured_review")
    return decision, evidence, score


def load_existing(session):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError("Live duplicate lookup requires Supabase configuration")
    rows = []
    for table in ("arash_jobs", "arash_notification_history"):
        offset = 0
        while True:
            history = table.endswith("history")
            columns = ("source,job_id,title:title_key,company:company_key,location:location_key,url:url_key,notification_status:outcome"
                       if history else "source,job_id,title,company,location,url,status,sent_to_telegram,notification_status,decision_evidence")
            r = session.get(SUPABASE_URL + "/rest/v1/" + table,
                headers={"apikey": SUPABASE_SECRET_KEY}, params={"select": columns,
                "company_key" if history else "company": "ilike.FERCHAU*",
                "order": "job_id.asc", "limit": 500, "offset": offset}, timeout=20)
            if r.status_code != 200:
                raise RuntimeError("FERCHAU duplicate lookup failed: HTTP " + str(r.status_code))
            batch = r.json()
            rows.extend(batch)
            if len(batch) < 500:
                break
            offset += len(batch)
    return rows


def duplicate(job, existing):
    incoming = job.get("_decision_evidence") or job.get("decision_evidence") or {}
    incoming_ref = reference(job.get("requisition_id", "") + " " +
                             job.get("description", "") + " " + incoming.get("description", ""))
    for row in existing:
        if not was_notified(row):
            continue
        if row.get("source") == job["source"] and str(row.get("job_id")) == job["job_id"]:
            return True
        evidence = row.get("decision_evidence") or {}
        ref = reference(evidence.get("requisition_id", "") + " " + evidence.get("description", ""))
        if ref and ref == incoming_ref:
            return True
        a, b = normalized_title(job["title"]), normalized_title(row.get("title", ""))
        left, right = city(job["location"]), city(row.get("location", ""))
        if a and b and (left == right or not left or not right) and SequenceMatcher(None, a, b).ratio() >= .78:
            return True
    return False


def run(session, existing, max_pages=20, pause=.2):
    jobs, seen, complete = [], set(), False
    cutoff = datetime.now(timezone.utc).timestamp() - 86400
    previous = float("inf")
    for page in range(max_pages):
        response = session.get(BASE + "/de/en/", params={"type": 3,
            "sortingType": "actuality", "sortingDirection": "DESC", "offset": page*25}, timeout=25)
        response.raise_for_status()
        data = page_data(response.text)["Data"]
        offers = data["Offers"]
        if not offers and (page*25 < data["OffersCount"]["total"]):
            raise ValueError("Listing unexpectedly empty")
        boundary = False
        for item in offers:
            edited = float(item["edited"])
            if edited > previous:
                raise ValueError("Publication-window scan requires descending edit order")
            previous = edited
            if str(item["id"]) in seen:
                raise ValueError("Repeated FERCHAU pagination")
            seen.add(str(item["id"]))
            if edited < cutoff:
                boundary = True
                continue
            job = candidate(item)
            if not job or excluded_title_reason(job["title"]) or delivery_block_reason(job):
                continue
            job = fetch_details(session, job)
            decision, evidence, score = assess(job)
            jobs.append({**job, "decision": decision, "evidence": evidence, "score": score,
                         "duplicate": duplicate(job, existing)})
            time.sleep(pause)
        if boundary or len(seen) >= data["OffersCount"]["total"]:
            complete = True
            break
        time.sleep(pause)
    if not complete:
        raise ValueError("Page limit reached before fresh window complete; no publication")
    return {"summary": {"mode": "dry_run", "pages": page+1, "listing_rows": len(seen),
        "details_checked": len(jobs), "decisions": dict(Counter(j["decision"] for j in jobs)),
        "duplicate_holds": sum(j["duplicate"] for j in jobs), "messages_sent": 0}, "jobs": jobs}


def publish(report, session):
    for job in report["jobs"]:
        if job["decision"] == "reject" or not recent(job) or delivery_block_reason(job):
            continue
        if duplicate(job, load_existing(session)):
            continue
        save_job("ferchau", job["job_id"], title=job["title"], company=job["company"],
            location=job["location"], url=job["url"], posted_at=job["posted_at"],
            match_score=job["score"], status=("apply" if job["decision"] == "apply" else "manual_review") + "@" + MATCHER_REVISION)
        record_decision("ferchau", job["job_id"], job["decision"], job["score"], job["evidence"])
        label = "MATCH" if job["decision"] == "apply" else "MANUAL REVIEW"
        message = (f"FERCHAU — {label}\n{job['title']}\n{job['location']}\n"
                   f"Published: {job['posted_at']}\n{job['evidence']['reason']}\n{job['url']}")
        report["summary"]["messages_sent"] += bool(notify_job_once(job, message, send_telegram))
    report["summary"]["mode"] = "production"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post", action="store_true")
    parser.add_argument("--existing-jobs", type=Path, help="Dry-run snapshot only")
    parser.add_argument("--output", type=Path, default=Path("ferchau_audit.json"))
    parser.add_argument("--max-pages", type=int, default=20)
    args = parser.parse_args()
    if args.max_pages < 1 or (args.post and args.existing_jobs):
        parser.error("Positive page limit and live history required for posting")
    with requests.Session() as session:
        session.headers["User-Agent"] = "ArashJobRadar/1.0 (FERCHAU vacancy monitor)"
        existing = json.loads(args.existing_jobs.read_text()) if args.existing_jobs else load_existing(session)
        report = run(session, existing, args.max_pages)
        if args.post:
            publish(report, session)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
