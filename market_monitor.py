import hashlib
import html
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import BOT_TOKEN, CHAT_ID
from profile import ARASH_EXPERIENCE_YEARS, EXCLUDE_WORDS, MIN_MATCH_PERCENT, SENIOR_MIN_MATCH_PERCENT
from job_matcher import (
    contract_status as cv_contract_status,
    evaluate_fit as cv_evaluate_fit,
    experience_status as cv_experience_status,
    extract_candidate_experience_years as cv_extract_candidate_experience_years,
    german_requirement as cv_german_requirement,
    is_senior_title as cv_is_senior_title,
    location_status as cv_location_status,
    security_warnings as cv_security_warnings,
)
from supabase_store import (
    find_sent_duplicate,
    get_job_record,
    save_job,
    update_job,
)

REVISION = "2026-09-30-b"
MAX_JOB_AGE_DAYS = 3
MAX_NEW_DETAILS_PER_SOURCE = 20
TELEGRAM_MAX = 3900
TERMS_PER_RUN = 3

SEARCH_TERMS = [
    "Development Engineer",
    "Entwicklungsingenieur",
    "Test Engineer",
    "Testingenieur",
    "Test and Validation Engineer",
    "System Test Engineer",
    "System Integration Engineer",
    "Validation Engineer",
    "Verification Engineer",
    "HIL Test Engineer",
    "ADAS Test Engineer",
    "ECU Diagnostics Engineer",
]


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def excluded(text):
    low = (text or "").lower()
    return any(word in low for word in EXCLUDE_WORDS)


def parse_date(value):
    value = clean(value)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def is_recent(value):
    dt = parse_date(value)
    if dt is None:
        return True
    age = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    return age <= MAX_JOB_AGE_DAYS + 1


def find_job_posting(data):
    if isinstance(data, dict):
        t = data.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            return data
        for value in data.values():
            found = find_job_posting(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_job_posting(item)
            if found:
                return found
    return None


TASK_HEADINGS = [
    "aufgaben", "deine aufgaben", "ihre aufgaben", "das erwartet dich",
    "das erwartet sie", "responsibilities", "your responsibilities",
    "what you will do", "what you'll do", "your tasks", "tätigkeiten",
]
REQ_HEADINGS = [
    "anforderungen", "qualifikation", "qualifikationen", "dein profil",
    "ihr profil", "das bringst du mit", "das bringen sie mit",
    "was du mitbringst", "was sie mitbringen", "requirements",
    "qualifications", "your profile", "what you bring", "who you are",
]
BENEFIT_HEADINGS = [
    "benefits", "wir bieten", "das bieten wir", "was wir bieten",
    "what we offer", "our benefits",
]


def heading_type(text):
    low = clean(text).lower()
    if any(x in low for x in TASK_HEADINGS):
        return "tasks"
    if any(x in low for x in REQ_HEADINGS):
        return "requirements"
    if any(x in low for x in BENEFIT_HEADINGS):
        return "benefits"
    return "other"


def unique(items):
    out, seen = [], set()
    for item in items:
        item = clean(item)
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def extract_sections(description_html):
    result = {"tasks": [], "requirements": [], "benefits": [], "other": []}
    soup = BeautifulSoup(description_html or "", "html.parser")
    current = "other"

    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b", "li", "p"]):
        text = clean(el.get_text(" ", strip=True))
        if not text:
            continue

        if el.name in {"h1", "h2", "h3", "h4", "h5"}:
            section = heading_type(text)
            if section != "other":
                current = section
            continue

        if el.name in {"strong", "b"} and len(text) <= 120:
            section = heading_type(text)
            if section != "other":
                current = section
                continue

        if el.name == "li" or (el.name == "p" and len(text) >= 35):
            result[current].append(text)

    return {key: unique(value) for key, value in result.items()}


def build_location(posting):
    location_type = clean(posting.get("jobLocationType", "")).upper()
    if "TELECOMMUTE" in location_type:
        return "Remote Germany"

    locations = posting.get("jobLocation", [])
    if isinstance(locations, dict):
        locations = [locations]

    output = []
    for item in locations:
        if not isinstance(item, dict):
            continue
        address = item.get("address", {})
        if not isinstance(address, dict):
            continue
        country = address.get("addressCountry", "")
        if isinstance(country, dict):
            country = country.get("name", "") or country.get("addressCountry", "")
        pieces = [
            clean(address.get("addressLocality", "")),
            clean(address.get("addressRegion", "")),
            clean(country),
        ]
        value = ", ".join(x for x in pieces if x)
        if value and value not in output:
            output.append(value)
    return " / ".join(output)


def build_company(posting):
    org = posting.get("hiringOrganization", {})
    if isinstance(org, dict):
        return clean(org.get("name", ""))
    return clean(org)


def build_employment(posting):
    value = posting.get("employmentType", "")
    if isinstance(value, list):
        return ", ".join(clean(x) for x in value if clean(x))
    return clean(value)


def get_job_details(page, candidate):
    try:
        response = page.goto(candidate["url"], wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(900)
    except Exception as exc:
        print("  Detail navigation error:", exc)
        return None

    if response is not None and response.status >= 400:
        print("  Detail HTTP:", response.status)
        return None

    source_html = page.content()
    low = source_html.lower()
    if any(x in low for x in [
        "additional verification required", "verify you are human",
        "unusual traffic", "access denied",
    ]):
        print("  Anti-bot/challenge page detected.")
        return None

    soup = BeautifulSoup(source_html, "html.parser")
    posting = None
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            posting = find_job_posting(json.loads(raw))
        except Exception:
            posting = None
        if posting:
            break

    if not posting:
        print("  No JobPosting JSON-LD found.")
        return None

    description_html = posting.get("description", "") or ""
    description = clean(BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True))
    if len(description) < 80:
        print("  Description too short.")
        return None

    sections = extract_sections(description_html)
    return {
        "title": clean(posting.get("title", "")) or candidate.get("title", ""),
        "company": build_company(posting),
        "location": build_location(posting),
        "date_posted": clean(posting.get("datePosted", "")),
        "employment_type": build_employment(posting),
        "description": description,
        **sections,
    }


def stepstone_urls(query):
    slug = quote(query.lower().replace(" ", "-"), safe="-")
    base = "https://www.stepstone.de/jobs/" + slug
    return [
        ("Munich", base + "/in-m%C3%BCnchen?radius=100&sort=2"),
        ("Nuremberg", base + "/in-n%C3%BCrnberg?radius=30&sort=2"),
        ("Remote", base + "/remote"),
    ]


def indeed_urls(query):
    base = "https://de.indeed.com/jobs?"
    return [
        ("Munich", base + urlencode({"q": query, "l": "München", "radius": "100", "fromage": "3", "sort": "date"})),
        ("Nuremberg", base + urlencode({"q": query, "l": "Nürnberg", "radius": "30", "fromage": "3", "sort": "date"})),
        ("Remote", base + urlencode({"q": query + " remote", "l": "Deutschland", "fromage": "3", "sort": "date"})),
    ]


def stepstone_id(url):
    match = re.search(r"--(\d{6,})(?:-inline)?\.html", url, re.I)
    if match:
        return match.group(1)
    match = re.search(r"/job/(\d{6,})", url, re.I)
    if match:
        return match.group(1)
    return hashlib.sha1(url.encode()).hexdigest()[:20]


def indeed_id(url, element=None):
    if element is not None:
        try:
            value = element.get_attribute("data-jk") or ""
            if value:
                return value
        except Exception:
            pass
    parsed = parse_qs(urlparse(url).query)
    for key in ("jk", "vjk"):
        if parsed.get(key):
            return parsed[key][0]
    return hashlib.sha1(url.encode()).hexdigest()[:20]


def collect_stepstone(page, query):
    jobs = {}
    for label, url in stepstone_urls(query):
        print("  StepStone search:", query, "|", label)
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1200)
        except Exception as exc:
            print("   Search error:", exc)
            continue
        if response is not None and response.status >= 400:
            print("   HTTP:", response.status)
            continue

        anchors = page.locator('a[href*="/stellenangebote--"], a[href*="-inline.html"], a[href*="/job/"]')
        found = 0
        for i in range(min(anchors.count(), 80)):
            a = anchors.nth(i)
            try:
                href = clean(a.get_attribute("href"))
                title = clean(a.inner_text())
            except Exception:
                continue
            if not href:
                continue
            full = urljoin("https://www.stepstone.de", href)
            if "/jobs/" in urlparse(full).path.lower():
                continue
            jid = stepstone_id(full)
            if jid not in jobs:
                jobs[jid] = {
                    "source": "stepstone", "source_name": "STEPSTONE",
                    "job_id": jid, "title": title, "url": full,
                    "query": query, "search_area": label,
                }
                found += 1
        print("   Candidate links:", found)
    return list(jobs.values())


def collect_indeed(page, query):
    jobs = {}
    for label, url in indeed_urls(query):
        print("  Indeed search:", query, "|", label)
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1400)
        except Exception as exc:
            print("   Search error:", exc)
            continue
        if response is not None and response.status >= 400:
            print("   HTTP:", response.status)
            continue

        body = page.content().lower()
        if any(x in body for x in ["additional verification required", "verify you are human"]):
            print("   Indeed challenge page.")
            continue

        anchors = page.locator('a[href*="/viewjob"], a[href*="/rc/clk"], a[data-jk]')
        found = 0
        for i in range(min(anchors.count(), 80)):
            a = anchors.nth(i)
            try:
                href = clean(a.get_attribute("href"))
                title = clean(a.inner_text())
            except Exception:
                continue
            if not href:
                continue
            full = urljoin("https://de.indeed.com", href)
            jid = indeed_id(full, a)
            if jid not in jobs:
                jobs[jid] = {
                    "source": "indeed", "source_name": "INDEED",
                    "job_id": jid, "title": title,
                    "url": "https://de.indeed.com/viewjob?jk=" + jid,
                    "query": query, "search_area": label,
                }
                found += 1
        print("   Candidate links:", found)
    return list(jobs.values())


def should_process(candidate):
    record = get_job_record(candidate["source"], candidate["job_id"])
    if not record:
        return True
    status = record.get("status", "") or ""
    if record.get("sent_to_telegram") or status == "sent":
        return False
    tag = "@" + REVISION
    if status.startswith("rejected_") and not status.endswith(tag):
        print("  Rechecking old rejection after matcher update.")
        return True
    return False


def remember(candidate, details, status, score=None, sent=False):
    stored_status = "sent" if sent else (
        status + "@" + REVISION if status.startswith("rejected_") else status
    )
    details = details or {}
    payload = {
        "source": candidate["source"],
        "job_id": candidate["job_id"],
        "title": details.get("title", "") or candidate.get("title", ""),
        "company": details.get("company", ""),
        "location": details.get("location", ""),
        "url": candidate["url"],
        "posted_at": details.get("date_posted", ""),
        "match_score": score,
        "status": stored_status,
        "sent_to_telegram": sent,
    }

    if save_job(**payload):
        print("  Saved:", stored_status)
        return

    update_job(
        candidate["source"],
        candidate["job_id"],
        match_score=score,
        status=stored_status,
        sent_to_telegram=sent,
        posted_at=details.get("date_posted", ""),
    )
    print("  Updated:", stored_status)


def send_telegram(text):
    response = requests.post(
        "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": False},
        timeout=25,
    )
    print("  Telegram:", response.status_code)
    return response.status_code == 200


def send_long(text):
    if len(text) <= TELEGRAM_MAX:
        return send_telegram(text)
    chunks, current = [], ""
    for line in text.splitlines():
        test = current + line + "\n"
        if len(test) > TELEGRAM_MAX:
            if current.strip():
                chunks.append(current.strip())
            current = line + "\n"
        else:
            current = test
    if current.strip():
        chunks.append(current.strip())
    for i, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            chunk = f"Part {i}/{len(chunks)}\n\n" + chunk
        if not send_telegram(chunk):
            return False
    return True


def add_bullets(text, heading, items, limit=12):
    if not items:
        return text
    text += "\n" + heading + "\n"
    for item in items[:limit]:
        text += "• " + item + "\n"
    return text


def build_message(candidate, details, score, matched, years, exp_text, loc_text, german_text, contract_text, warnings, breakdown):
    years_text = "Not explicitly stated" if years is None else f"{years}+ years"
    text = (
        f"🚨 NEW {candidate['source_name']} JOB\n\n"
        f"💼 {details['title']}\n"
        f"🏢 {details['company'] or 'Not stated'}\n"
        f"📍 {details['location'] or 'Not stated'}\n"
        f"🏠 {loc_text}\n"
        f"📅 Posted: {details['date_posted'] or 'Not stated'}\n"
        f"💼 Employment: {contract_text}\n\n"
        f"🎯 CV MATCH: {score}%\n"
        f"• Requirements: {breakdown.get('requirements', 0)}%\n"
        f"• Core requirements: {breakdown.get('core_requirements', 0)}%\n"
        f"• Responsibilities: {breakdown.get('responsibilities', 0)}%\n"
        f"• Role: {breakdown.get('role', 0)}%\n"
    )

    reqs = breakdown.get("requirement_details", [])
    supported = [x for x in reqs if x.get("weight", 0) > 0 and x.get("score", 0) >= 70]
    gaps = [x for x in reqs if x.get("weight", 0) > 0 and x.get("score", 0) < 70]

    if supported:
        text += "\n✅ REQUIREMENTS SUPPORTED\n"
        for item in supported[:8]:
            text += f"• {item['score']}% — {item['text']}\n"
    if gaps:
        text += "\n❌ REQUIREMENT GAPS\n"
        for item in gaps[:8]:
            text += f"• {item['score']}% — {item['text']}\n"

    text += "\n✅ MATCHED SKILLS\n"
    if matched:
        for item in matched[:16]:
            text += "• " + item + "\n"
    else:
        text += "• No explicit tool keyword; fit comes from role/responsibilities\n"

    text += (
        f"\n⏳ EXPERIENCE\n"
        f"• Arash: ~{ARASH_EXPERIENCE_YEARS:g} years\n"
        f"• Job asks: {years_text}\n"
        f"• Assessment: {exp_text}\n\n"
        f"🌐 LANGUAGE\n"
        f"• German: {german_text}\n"
    )

    if warnings:
        text += "\n⚠️ WARNINGS\n"
        for warning in warnings[:10]:
            text += "• " + warning + "\n"

    text = add_bullets(text, "📋 RESPONSIBILITIES", details["tasks"])
    text = add_bullets(text, "🎓 REQUIREMENTS", details["requirements"])
    if not details["tasks"] and not details["requirements"]:
        text = add_bullets(text, "📄 JOB DETAILS", details["other"], 10)
    return text + "\n🔗 OPEN / APPLY\n" + candidate["url"]


def evaluate_candidate(page, candidate):
    print("\n" + "-" * 70)
    print(candidate["source_name"], "|", candidate.get("title", ""), "|", candidate["job_id"])

    if excluded(candidate.get("title", "")):
        print("  Rejected: excluded title.")
        remember(candidate, None, "rejected_title")
        return False

    details = get_job_details(page, candidate)
    if details is None:
        print("  Detail unavailable; not stored, will retry.")
        return False

    candidate["title"] = details["title"] or candidate.get("title", "")
    full_text = candidate["title"] + " " + details["description"]

    if excluded(details["employment_type"]):
        print("  Rejected employment type:", details["employment_type"])
        remember(candidate, details, "rejected_employment")
        return False

    if not is_recent(details["date_posted"]):
        print("  Rejected: older than", MAX_JOB_AGE_DAYS, "days.")
        remember(candidate, details, "rejected_age")
        return False

    loc_ok, loc_text = cv_location_status(details["location"], details["description"])

    # StepStone/Indeed location searches are themselves bounded. If the
    # source returned the job inside our Munich-radius or explicit Nuremberg
    # search, accept that source context even when the static city list does
    # not yet contain a nearby town such as Wessling, Kaufering or Manching.
    if (
        not loc_ok
        and candidate.get("search_area") == "Munich"
        and candidate.get("source") in {"stepstone", "indeed"}
        and "at" not in (details["location"] or "").lower()
        and "austria" not in (details["location"] or "").lower()
        and "österreich" not in (details["location"] or "").lower()
    ):
        loc_ok = True
        loc_text = "Within source Munich-radius search"

    if (
        not loc_ok
        and candidate.get("search_area") == "Nuremberg"
        and candidate.get("source") in {"stepstone", "indeed"}
        and "at" not in (details["location"] or "").lower()
        and "austria" not in (details["location"] or "").lower()
        and "österreich" not in (details["location"] or "").lower()
    ):
        loc_ok = True
        loc_text = "Accepted Nuremberg search area"

    if not loc_ok:
        print("  Rejected location:", loc_text, "|", details["location"])
        remember(candidate, details, "rejected_location")
        return False

    years = cv_extract_candidate_experience_years(details["requirements"], details["description"])
    reject_exp, exp_text = cv_experience_status(years)
    if reject_exp:
        print("  Rejected experience:", exp_text)
        remember(candidate, details, "rejected_experience")
        return False

    reject_contract, contract_text = cv_contract_status(
        {"employment type": details["employment_type"]},
        details["description"],
    )
    if reject_contract:
        print("  Rejected contract:", contract_text)
        remember(candidate, details, "rejected_employment")
        return False

    reject_lang, german_text, _ = cv_german_requirement(full_text)
    if reject_lang:
        print("  Rejected language:", german_text)
        remember(candidate, details, "rejected_language")
        return False

    score, matched, skill_warnings, breakdown = cv_evaluate_fit(
        candidate["title"], details["description"], details["requirements"], details["tasks"]
    )
    score = max(0, min(100, score))
    print("  Score:", score, "| req:", breakdown.get("requirements", 0), "| core:", breakdown.get("core_requirements", 0))

    if not breakdown.get("gates_pass", False):
        print(
            "  Rejected by requirement gates.",
            "| domain:",
            breakdown.get("domain_reason", ""),
        )
        remember(candidate, details, "rejected_requirements", score)
        return False

    if score < MIN_MATCH_PERCENT:
        print("  Rejected: score below threshold.")
        remember(candidate, details, "rejected_score", score)
        return False

    if cv_is_senior_title(candidate["title"]) and score < SENIOR_MIN_MATCH_PERCENT:
        print("  Rejected: senior/lead below threshold.")
        remember(candidate, details, "rejected_senior", score)
        return False

    duplicate = find_sent_duplicate(
        candidate["source"], details["title"], details["company"], details["location"]
    )
    if duplicate:
        print("  Cross-source duplicate of:", duplicate.get("source", ""), duplicate.get("job_id", ""))
        remember(candidate, details, "duplicate_cross_source", score)
        return False

    warnings = []
    if german_text.startswith("⚠️"):
        warnings.append(german_text)
    warnings.extend(skill_warnings)
    warnings.extend(cv_security_warnings(full_text))

    message = build_message(
        candidate, details, score, matched, years, exp_text, loc_text,
        german_text, contract_text, warnings, breakdown
    )
    print("  MATCH -> Telegram")
    if send_long(message):
        remember(candidate, details, "sent", score, True)
        return True

    print("  Telegram failed; not stored so it can retry.")
    return False


def current_terms():
    groups = [SEARCH_TERMS[i:i + TERMS_PER_RUN] for i in range(0, len(SEARCH_TERMS), TERMS_PER_RUN)]
    return groups[int(time.time() // 900) % len(groups)]


def run_source(browser, source, queries):
    context = browser.new_context(
        viewport={"width": 1440, "height": 1100},
        locale="de-DE",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        extra_http_headers={
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        },
    )
    search_page = context.new_page()
    detail_page = context.new_page()
    collected = {}

    for query in queries:
        try:
            jobs = collect_stepstone(search_page, query) if source == "stepstone" else collect_indeed(search_page, query)
        except Exception as exc:
            print(source, "search failure:", query, exc)
            continue
        for job in jobs:
            collected[job["job_id"]] = job

    print("\n", source.upper(), "UNIQUE CANDIDATES:", len(collected))
    to_check = []
    for candidate in collected.values():
        try:
            if should_process(candidate):
                to_check.append(candidate)
        except Exception as exc:
            print("Supabase lookup error:", exc)

    print(source.upper(), "NEW/RECHECK CANDIDATES:", len(to_check))
    sent = 0
    checked = 0

    for candidate in to_check[:MAX_NEW_DETAILS_PER_SOURCE]:
        checked += 1
        try:
            if evaluate_candidate(detail_page, candidate):
                sent += 1
        except Exception as exc:
            print("Candidate processing error:", candidate["job_id"], exc)
        detail_page.wait_for_timeout(700)

    search_page.close()
    detail_page.close()
    context.close()
    print(source.upper(), "SUMMARY | candidates:", len(collected), "| checked:", checked, "| sent:", sent)
    return source, len(collected), checked, sent


def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit("Telegram configuration missing.")

    queries = current_terms()
    print("\n" + "=" * 70)
    print("ARASH JOB RADAR - INDEED + STEPSTONE")
    print("Matcher revision:", REVISION)
    print("Search terms:", ", ".join(queries))
    print("=" * 70)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-http2"],
        )
        for source in ["stepstone", "indeed"]:
            try:
                results.append(run_source(browser, source, queries))
            except Exception as exc:
                print(source.upper(), "SOURCE FAILURE:", exc)
        browser.close()

    print("\n" + "=" * 70)
    print("MARKET RADAR SUMMARY")
    for source, candidates, checked, sent in results:
        print(source.upper(), "| candidates:", candidates, "| checked:", checked, "| sent:", sent)
    print("=" * 70)


if __name__ == "__main__":
    main()
