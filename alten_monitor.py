"""ALTEN collector. Read-only by default; --post enables eligible notifications.

Run: python alten_monitor.py --existing-jobs /path/to/snapshot.json
Without a snapshot, reads ALTEN records/history from the configured Supabase.
"""
import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import SUPABASE_URL, SUPABASE_SECRET_KEY, BOT_TOKEN, CHAT_ID
from decisions import fit_decision, record_decision
from notifications import notify_job_once, was_notified
from supabase_store import save_job
from job_matcher import (contract_status, evaluate_fit, experience_status,
                         extract_candidate_experience_years, german_requirement)
from profile import EXCLUDE_WORDS, MATCHER_REVISION

BASE = "https://www.alten-germany.de"
JOB_PATH = re.compile(r"^/(?:en/)?jobs/((?:\d{4}-\d+|\d{10,}))-[^/]+/$")


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_url(value):
    parsed = urlparse(value or "")
    return parsed.netloc.lower().removeprefix("www.") + parsed.path.rstrip("/")


def website_id(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.alten-germany.de":
        return None
    match = JOB_PATH.fullmatch(parsed.path)
    return match.group(1) if match else None


def search_url(page, distance=25):
    # A search string alone DOES NOT apply the website's radius filter.
    return BASE + "/en/jobs/?" + urlencode({
        "location[search]": "Munich", "location[lat]": "48.1351253",
        "location[lon]": "11.5819805", "distance": distance,
        "sortby": "date", "pagenum": page, "per_page": 25})


def date_iso(text):
    match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", text)
    return datetime.strptime(match[0], "%d/%m/%Y").date().isoformat() if match else ""


def parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    count = soup.select_one(".wp-block-jobboard-filter__counts .has-secondary-color")
    if count is None or not clean(count.get_text()).isdigit():
        raise ValueError("ALTEN listing markup missing; refusing a false empty success")
    jobs = {}
    for card in soup.select(".offer-list-item"):
        link = card.select_one("a.card-title[href]")
        if link is None:
            continue
        url = urljoin(BASE, link["href"])
        job_id = website_id(url)
        if job_id is None:
            continue
        location = card.select_one(".card-location .location-list")
        date = card.select_one(".card-date")
        jobs[job_id] = {"source": "alten", "job_id": job_id,
            "title": clean(link.get_text()), "company": "ALTEN",
            "location": clean(location.get_text()) if location else "",
            "posted_at": date_iso(date.get_text()) if date else "", "url": url}
    total = int(clean(count.get_text()))
    if total and not jobs:
        raise ValueError("ALTEN advertises results but no valid job cards were parsed")
    return list(jobs.values()), total


def parse_detail(html, candidate):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".is-style-page-title.wp-block-post-title")
    sections = {}
    for key, selector in (("tasks", ".offer-tasks-title"),
                          ("requirements", ".offer-requirements-title")):
        heading = soup.select_one(selector)
        if heading is None:
            raise ValueError("ALTEN detail missing " + key)
        block = heading.find_parent(class_="wp-block-jobboard-offer-meta")
        sections[key] = list(dict.fromkeys(clean(x.get_text(" ", strip=True))
                           for x in block.select("li") if clean(x.get_text())))
        if not sections[key]:
            raise ValueError("ALTEN detail has empty " + key)
    if title is None:
        raise ValueError("ALTEN detail title missing")
    description = "\n".join(clean(block.get_text(" ", strip=True))
                           for block in soup.select(".wp-block-jobboard-offer-meta"))
    def meta(label):
        element = soup.select_one('[title="' + label + '"]')
        return clean(element.get_text(" ", strip=True)) if element else ""
    reference = meta("Reference")
    return {**candidate, "title": clean(title.get_text()), **sections,
            "description": description, "requisition_id": reference,
            "location": meta("Location") or candidate["location"],
            "posted_at": date_iso(meta("Publication date")) or candidate["posted_at"]}


def normalized_title(value):
    value = value.casefold()
    value = re.sub(r"\([^)]*(?:gender|m/w|w/m|m/f)[^)]*\)", " ", value)
    value = value.replace("testingenieur", "test engineer").replace("münchen", "munich")
    value = re.sub(r"\b(?:gg|gl|gs|sz|dw|100|200|800)\b\s*$", "", value)
    return clean(re.sub(r"[^\w]+", " ", value))


def city(value):
    value = value.casefold().replace("münchen", "munich")
    if re.fullmatch(r"munich(?: bavaria)?(?: germany)?", value):
        return "munich"
    return clean(re.sub(r"\s*\([^)]*\)", "", value.split(",")[0]))


def duplicate_check(job, existing):
    """All existing statuses count, including pending/manual and uncertain sends.

    Similar titles are held as POSSIBLE duplicates, never asserted identical.
    This is pilot evidence, not an atomic cross-source notification reservation.
    """
    possible = None
    for other in existing:
        if (other.get("source"), str(other.get("job_id"))) == (job["source"], str(job["job_id"])):
            continue
        if not re.match(r"^alten\b", other.get("company", ""), re.I):
            continue
        reason = None
        if canonical_url(job["url"]) == canonical_url(other.get("url")):
            reason = "same_url"
        elif website_id(other.get("url", "")) == job["job_id"]:
            reason = "same_website_id"
        elif job.get("requisition_id") and re.search(
            r"(?<!\w)" + re.escape(job["requisition_id"]) + r"(?!\w)",
            other.get("description") or "", re.I):
            reason = "same_requisition"
        same_city = city(job["location"]) == city(other.get("location", ""))
        a, b = normalized_title(job["title"]), normalized_title(other.get("title", ""))
        if not reason and same_city and a and a == b:
            # Same title/location can still represent distinct client projects.
            possible = {"state": "possible_duplicate", "reason": "same_title_location",
                        "source": other.get("source"), "job_id": other.get("job_id")}
        elif not reason and same_city and a and b and SequenceMatcher(None, a, b).ratio() >= .78:
            possible = {"state": "possible_duplicate", "reason": "similar_title_location",
                        "source": other.get("source"), "job_id": other.get("job_id")}
        if reason:
            return {"state": "duplicate", "reason": reason,
                    "source": other.get("source"), "job_id": other.get("job_id")}
    return possible or {"state": "no_match_found"}


def assess(job, max_age_hours=24, now=None):
    now = now or datetime.now(timezone.utc)
    if not job["posted_at"]:
        return {"decision": "manual", "reason": "unknown_publication_date"}
    posted = datetime.fromisoformat(job["posted_at"]).replace(tzinfo=timezone.utc)
    age = (now - posted).total_seconds() / 3600
    if age < 0:
        return {"decision": "manual", "reason": "future_publication_date"}
    if age > max_age_hours:
        return {"decision": "reject", "reason": "older_than_age_limit"}
    if any(word in job["title"].lower() for word in EXCLUDE_WORDS):
        return {"decision": "reject", "reason": "excluded_title"}
    if re.search(r"business manager|account manager|manager sales|manager competence center|assistenz", job["title"], re.I):
        return {"decision": "reject", "reason": "sales_or_administrative_role"}
    if not job.get("description"):
        return {"decision": "manual", "reason": "detail_not_fetched"}
    text = job["description"]
    if german_requirement(text)[0]:
        return {"decision": "reject", "reason": "mandatory_advanced_german"}
    if contract_status({}, text)[0]:
        return {"decision": "reject", "reason": "contract"}
    years = extract_candidate_experience_years(job["requirements"], text)
    if experience_status(years)[0]:
        return {"decision": "reject", "reason": "experience"}
    score, _, _, breakdown = evaluate_fit(job["title"], text, job["requirements"], job["tasks"])
    decision, reason = fit_decision(job["title"], score, breakdown)
    return {"decision": decision, "reason": reason, "score": score, "breakdown": breakdown}


def load_existing(session):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError("Provide --existing-jobs or Supabase read credentials")
    rows = []
    headers = {"apikey": SUPABASE_SECRET_KEY}
    for table in ("arash_jobs", "arash_notification_history"):
        offset = 0
        while True:
            columns = "source,job_id,title,company,location,url"
            if table == "arash_jobs":
                columns += ",status,sent_to_telegram,notification_status,decision_evidence"
                company_field = "company"
            else:
                columns = "source,job_id,title:title_key,company:company_key,location:location_key,url:url_key,status:outcome,notification_status:outcome"
                company_field = "company_key"
            response = session.get(SUPABASE_URL + "/rest/v1/" + table,
                headers=headers, params={"select": columns, company_field: "ilike.ALTEN*",
                                         "order": "job_id.asc", "limit": 500, "offset": offset}, timeout=20)
            if response.status_code != 200:
                # Do not print response bodies or request headers containing secrets.
                raise RuntimeError("Duplicate lookup failed: " + table + " HTTP " + str(response.status_code))
            batch = response.json()
            for row in batch:
                row["description"] = (row.pop("decision_evidence", None) or {}).get("description", "")
            rows.extend(batch)
            if len(batch) < 500:
                break
            offset += len(batch)
    return rows


def run(session, existing, max_pages=5, max_details=12, max_age_hours=24, pause=.4):
    started = time.monotonic()
    jobs, pages, total = {}, 0, None
    for number in range(1, max_pages + 1):
        response = session.get(search_url(number), timeout=25)
        response.raise_for_status()
        page_jobs, total = parse_listing(response.text)
        new = [job for job in page_jobs if job["job_id"] not in jobs]
        if not new and len(jobs) < total:
            raise RuntimeError("ALTEN pagination repeated or ended before all results were collected")
        jobs.update({job["job_id"]: job for job in new})
        pages += 1
        if len(jobs) >= total:
            break
        time.sleep(pause)
    results, detail_count, errors = [], 0, []
    for candidate in sorted(jobs.values(), key=lambda job: job["posted_at"], reverse=True):
        # Old/excluded jobs need no costly detail request. Fresh candidates get
        # full tasks and requirements before the existing matcher is called.
        preliminary = assess(candidate, max_age_hours)
        if preliminary["reason"] == "detail_not_fetched" and detail_count < max_details:
            detail_count += 1
            try:
                response = session.get(candidate["url"], timeout=25)
                response.raise_for_status()
                candidate = parse_detail(response.text, candidate)
            except (requests.RequestException, ValueError) as exc:
                errors.append({"job_id": candidate["job_id"], "error": type(exc).__name__})
            time.sleep(pause)
        results.append({**candidate, "duplicate_check": duplicate_check(candidate, existing),
                        "assessment": assess(candidate, max_age_hours)})
    summary = {"mode": "read_only_pilot", "matcher_revision": MATCHER_REVISION,
        "search_url": search_url(1), "radius_km": 25,
        "max_age_hours": max_age_hours,
        "date_precision": "website gives dates only; UTC midnight used conservatively",
        "listed": len(jobs), "reported_total": total, "pages": pages,
        "listing_complete": len(jobs) >= total, "details_checked": detail_count,
        "existing_records_checked": len(existing), "detail_errors": errors,
        "decisions": dict(Counter(x["assessment"]["decision"] for x in results)),
        "duplicate_states": dict(Counter(x["duplicate_check"]["state"] for x in results)),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "telegram_messages_sent": 0, "database_writes": 0}
    return {"summary": summary, "jobs": results}


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing Telegram configuration")
    # One attempt only. The permanent reservation blocks retries after timeout.
    response = requests.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
        data={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True}, timeout=20)
    response.raise_for_status()
    return response.json().get("ok") is True


def publish(report, session):
    if not report["summary"]["listing_complete"]:
        raise RuntimeError("Incomplete listing; refusing publication")
    sent, held = 0, 0
    for job in report["jobs"]:
        assessment = job["assessment"]
        if assessment["decision"] not in {"apply", "manual"} or not job.get("description"):
            continue
        # Recheck age and history immediately before storing/enqueueing.
        assessment = assess(job)
        if assessment["decision"] == "reject":
            continue
        existing = load_existing(session)
        if any(row.get("source") == "alten" and str(row.get("job_id")) == str(job["job_id"])
               and was_notified(row) for row in existing):
            held += 1
            continue
        duplicate = duplicate_check(job, existing)
        if duplicate["state"] != "no_match_found":
            held += 1
            continue
        save_job("alten", job["job_id"], title=job["title"], company=job["company"],
            location=job["location"], url=job["url"], posted_at=job["posted_at"],
            match_score=assessment.get("score"),
            status=("apply" if assessment["decision"] == "apply" else "review_required") + "@" + MATCHER_REVISION)
        evidence = {**assessment, "description": job["description"],
            "requirements": job["requirements"], "tasks": job["tasks"],
            "requisition_id": job.get("requisition_id", ""), "stage": "first_match"}
        record_decision("alten", job["job_id"], assessment["decision"], assessment.get("score"), evidence)
        if assessment["decision"] == "apply":
            message = ("✅ ALTEN JOB — " + str(assessment.get("score", "")) + "%\n" +
                job["title"] + "\nALTEN · " + job["location"] + "\n" + assessment["reason"] + "\n" + job["url"])
            sent += bool(notify_job_once(job, message, send_telegram))
    report["summary"].update(mode="production", telegram_messages_sent=sent,
                            duplicate_holds=held)
    report["summary"].pop("database_writes", None)
    return sent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-jobs", type=Path)
    parser.add_argument("--output", type=Path, default=Path("alten_audit.json"))
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--max-details", type=int, default=12)
    parser.add_argument("--max-age-hours", type=float, default=24)
    parser.add_argument("--post", action="store_true")
    args = parser.parse_args()
    if args.max_pages < 1 or args.max_details < 1 or args.max_age_hours <= 0:
        parser.error("limits must be positive")
    if args.post and (args.existing_jobs or args.max_age_hours != 24):
        parser.error("posting requires live duplicate lookup and the 24-hour cutoff")
    with requests.Session() as session:
        session.headers["User-Agent"] = "ArashJobRadar/1.0 (ALTEN read-only pilot)"
        existing = json.loads(args.existing_jobs.read_text()) if args.existing_jobs else load_existing(session)
        report = run(session, existing, args.max_pages, args.max_details, args.max_age_hours)
        if args.post:
            publish(report, session)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if report["summary"]["detail_errors"] or not report["summary"]["listing_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
