import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import BOT_TOKEN, CHAT_ID
from profile import (
    ARASH_EXPERIENCE_YEARS,
    MIN_MATCH_PERCENT,
    SENIOR_MIN_MATCH_PERCENT,
    EXCLUDE_WORDS,
)
from job_matcher import (
    evaluate_fit,
    extract_candidate_experience_years,
    experience_status,
    german_requirement,
    contract_status,
    location_status,
    is_senior_title,
    security_warnings,
)
from supabase_store import (
    get_job_record,
    save_job,
    update_job,
)


MATCHER_REVISION = "2026-09-30-c"
MAX_AGE_DAYS = 1
TELEGRAM_LIMIT = 3900

# The existing cloud scheduler triggers this script from the BMW workflow.
# Run the external boards only once every 15 minutes, not every 5 minutes.
RUN_EXTERNAL = (
    os.getenv("FORCE_PUBLIC_SOURCES", "0") == "1"
    or int(time.time() // 300) % 3 == 0
)

QUERY_GROUPS = [
    [
        "entwicklungsingenieur",
        "testingenieur",
        "system integration engineer",
        "validation engineer",
    ],
    [
        "system test engineer",
        "requirements engineer",
        "hil test engineer",
        "automotive test engineer",
    ],
]

QUERIES = QUERY_GROUPS[
    int(time.time() // 900)
    % len(QUERY_GROUPS)
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def send_telegram(text):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": False,
            },
            timeout=25,
        )
        print("Telegram:", response.status_code)
        return response.status_code == 200
    except Exception as exc:
        print("Telegram error:", exc)
        return False


def send_long(text):
    if len(text) <= TELEGRAM_LIMIT:
        return send_telegram(text)

    chunks = []
    current = ""

    for line in text.splitlines():
        candidate = current + line + "\n"

        if len(candidate) > TELEGRAM_LIMIT and current:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current = candidate

    if current.strip():
        chunks.append(current.strip())

    ok = True

    for index, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            chunk = f"Part {index}/{len(chunks)}\n\n" + chunk

        if not send_telegram(chunk):
            ok = False

    return ok


def extract_jobposting(data):
    if isinstance(data, dict):
        job_type = data.get("@type")

        if job_type == "JobPosting":
            return data

        if isinstance(job_type, list) and "JobPosting" in job_type:
            return data

        for value in data.values():
            found = extract_jobposting(value)

            if found:
                return found

    elif isinstance(data, list):
        for item in data:
            found = extract_jobposting(item)

            if found:
                return found

    return None


def fetch_html(url, browser_fallback=False):
    try:
        response = SESSION.get(
            url,
            timeout=25,
        )

        if response.status_code == 200 and len(response.text) > 1000:
            return response.text

        print("HTTP", response.status_code, url)

    except Exception as exc:
        print("Request error:", exc, url)

    if not browser_fallback:
        return ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={
                    "width": 1400,
                    "height": 1000,
                }
            )
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(3500)
            html = page.content()
            browser.close()
            return html

    except Exception as exc:
        print("Browser fallback error:", exc, url)
        return ""


def relative_or_absolute(base, href):
    return urljoin(
        base,
        href,
    )


def stepstone_search(query):
    slug = quote(
        query.lower().replace(" ", "-"),
        safe="-",
    )

    urls = [
        (
            "https://www.stepstone.de/jobs/"
            f"{slug}/in-m%C3%BCnchen"
            "?radius=100&sort=2"
        ),
        (
            "https://www.stepstone.de/jobs/"
            f"{slug}/in-n%C3%BCrnberg"
            "?radius=30&sort=2"
        ),
    ]

    jobs = {}

    for search_url in urls:
        html = fetch_html(
            search_url
        )

        if not html:
            continue

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        for link in soup.find_all(
            "a",
            href=True,
        ):
            href = clean(
                link.get(
                    "href",
                    ""
                )
            )

            if (
                "/stellenangebote--"
                not in href
                or "-inline.html"
                not in href
            ):
                continue

            url = relative_or_absolute(
                "https://www.stepstone.de",
                href,
            )

            match = re.search(
                r"--(\d+)-inline\.html",
                url,
            )

            if not match:
                continue

            job_id = match.group(1)
            title = clean(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            jobs[job_id] = {
                "source": "stepstone",
                "job_id": job_id,
                "title": title,
                "url": url,
            }

    return list(
        jobs.values()
    )


def indeed_job_key(href):
    parsed = urlparse(
        href
    )
    params = parse_qs(
        parsed.query
    )

    for key in [
        "jk",
        "vjk",
    ]:
        values = params.get(
            key
        )

        if values:
            return values[0]

    match = re.search(
        r"[?&](?:jk|vjk)=([A-Za-z0-9]+)",
        href,
    )

    return (
        match.group(1)
        if match
        else ""
    )


def indeed_search(query):
    urls = [
        (
            "https://de.indeed.com/jobs?"
            f"q={quote(query)}"
            "&l=M%C3%BCnchen"
            "&radius=100"
            "&fromage=1"
            "&sort=date"
        ),
        (
            "https://de.indeed.com/jobs?"
            f"q={quote(query)}"
            "&l=N%C3%BCrnberg"
            "&radius=25"
            "&fromage=1"
            "&sort=date"
        ),
    ]

    jobs = {}

    for search_url in urls:
        html = fetch_html(
            search_url,
            browser_fallback=True,
        )

        if not html:
            continue

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        for link in soup.find_all(
            "a",
            href=True,
        ):
            href = clean(
                link.get(
                    "href",
                    ""
                )
            )

            job_id = indeed_job_key(
                href
            )

            if not job_id:
                continue

            title = clean(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            url = (
                "https://de.indeed.com/viewjob?"
                f"jk={job_id}"
            )

            jobs[job_id] = {
                "source": "indeed",
                "job_id": job_id,
                "title": title,
                "url": url,
            }

    return list(
        jobs.values()
    )


def classify_heading(text):
    low = clean(
        text
    ).lower()

    task_terms = [
        "aufgaben",
        "deine aufgaben",
        "ihre aufgaben",
        "responsibilities",
        "your responsibilities",
        "what you will do",
        "tätigkeiten",
    ]

    requirement_terms = [
        "anforderungen",
        "dein profil",
        "ihr profil",
        "qualifikation",
        "qualifikationen",
        "requirements",
        "qualifications",
        "your profile",
        "what you bring",
    ]

    benefit_terms = [
        "benefits",
        "wir bieten",
        "das bieten wir",
        "what we offer",
    ]

    if any(
        term in low
        for term in requirement_terms
    ):
        return "requirements"

    if any(
        term in low
        for term in task_terms
    ):
        return "tasks"

    if any(
        term in low
        for term in benefit_terms
    ):
        return "benefits"

    return "other"


def extract_sections(description_html):
    soup = BeautifulSoup(
        description_html or "",
        "html.parser",
    )

    result = {
        "tasks": [],
        "requirements": [],
        "benefits": [],
        "other": [],
    }

    current = "other"

    for element in soup.find_all(
        [
            "h2",
            "h3",
            "h4",
            "strong",
            "b",
            "li",
            "p",
        ]
    ):
        text = clean(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if element.name in [
            "h2",
            "h3",
            "h4",
        ]:
            found = classify_heading(
                text
            )

            if found != "other":
                current = found

            continue

        if (
            element.name
            in [
                "strong",
                "b",
            ]
            and len(text) <= 120
        ):
            found = classify_heading(
                text
            )

            if found != "other":
                current = found
                continue

        if element.name == "li":
            result[current].append(
                text
            )

        elif (
            element.name == "p"
            and len(text) >= 35
        ):
            result[current].append(
                text
            )

    for key, values in result.items():
        unique = []
        seen = set()

        for value in values:
            norm = value.lower()

            if norm in seen:
                continue

            seen.add(
                norm
            )
            unique.append(
                value
            )

        result[key] = unique

    return result


def location_from_posting(posting):
    raw = posting.get(
        "jobLocation",
        []
    )

    if isinstance(
        raw,
        dict,
    ):
        raw = [
            raw
        ]

    locations = []

    for item in raw or []:
        if not isinstance(
            item,
            dict,
        ):
            continue

        address = item.get(
            "address",
            {}
        )

        if not isinstance(
            address,
            dict,
        ):
            continue

        country = address.get(
            "addressCountry",
            ""
        )

        if isinstance(
            country,
            dict,
        ):
            country = country.get(
                "name",
                ""
            )

        pieces = [
            clean(
                address.get(
                    "addressLocality",
                    ""
                )
            ),
            clean(
                address.get(
                    "addressRegion",
                    ""
                )
            ),
            clean(
                country
            ),
        ]

        value = ", ".join(
            part
            for part in pieces
            if part
        )

        if value:
            locations.append(
                value
            )

    return " / ".join(
        dict.fromkeys(
            locations
        )
    )


def get_details(job):
    html = fetch_html(
        job["url"],
        browser_fallback=(
            job["source"]
            == "indeed"
        ),
    )

    if not html:
        return None

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    posting = None

    for script in soup.find_all(
        "script",
        attrs={
            "type":
            "application/ld+json"
        },
    ):
        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(
                raw
            )
        except Exception:
            continue

        posting = extract_jobposting(
            data
        )

        if posting:
            break

    if not posting:
        print(
            "No JobPosting JSON-LD:",
            job["url"],
        )
        return None

    title = clean(
        posting.get(
            "title",
            ""
        )
    )

    hiring = posting.get(
        "hiringOrganization",
        {}
    )

    company = (
        clean(
            hiring.get(
                "name",
                ""
            )
        )
        if isinstance(
            hiring,
            dict,
        )
        else clean(
            hiring
        )
    )

    employment = posting.get(
        "employmentType",
        ""
    )

    if isinstance(
        employment,
        list,
    ):
        employment = ", ".join(
            str(item)
            for item in employment
        )

    description_html = posting.get(
        "description",
        ""
    )

    description_text = clean(
        BeautifulSoup(
            description_html,
            "html.parser",
        ).get_text(
            " ",
            strip=True,
        )
    )

    sections = extract_sections(
        description_html
    )

    return {
        "title": title or job.get(
            "title",
            ""
        ),
        "company": company,
        "location": location_from_posting(
            posting
        ),
        "date_posted": clean(
            posting.get(
                "datePosted",
                ""
            )
        ),
        "employment_type": clean(
            employment
        ),
        "description_text": description_text,
        **sections,
    }


def age_days(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except Exception:
        try:
            dt = datetime.strptime(
                value[:10],
                "%Y-%m-%d",
            ).replace(
                tzinfo=timezone.utc
            )
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return max(
        0,
        (
            datetime.now(
                timezone.utc
            )
            - dt
        ).days,
    )


def excluded_title(title):
    low = (
        title
        or ""
    ).lower()

    return any(
        term in low
        for term in EXCLUDE_WORDS
    )


def current_record(job):
    return get_job_record(
        job["source"],
        job["job_id"],
    )


def should_skip(job):
    record = current_record(
        job
    )

    if not record:
        return False

    status = (
        record.get(
            "status",
            ""
        )
        or ""
    )

    if (
        record.get(
            "sent_to_telegram"
        )
        or status == "sent"
    ):
        return True

    return status.endswith(
        "@"
        + MATCHER_REVISION
    )


def remember(
    job,
    details,
    status,
    score=None,
    sent=False,
):
    stored_status = (
        "sent"
        if sent
        else status
        + "@"
        + MATCHER_REVISION
    )

    record = current_record(
        job
    )

    if record:
        update_job(
            job["source"],
            job["job_id"],
            match_score=score,
            status=stored_status,
            sent_to_telegram=sent,
            posted_at=details.get(
                "date_posted",
                ""
            ),
        )
        return

    save_job(
        source=job["source"],
        job_id=job["job_id"],
        title=details.get(
            "title",
            job.get(
                "title",
                "",
            ),
        ),
        company=details.get(
            "company",
            "",
        ),
        location=details.get(
            "location",
            "",
        ),
        url=job["url"],
        posted_at=details.get(
            "date_posted",
            "",
        ),
        match_score=score,
        status=stored_status,
        sent_to_telegram=sent,
    )


def build_message(
    job,
    details,
    score,
    breakdown,
    required_years,
    experience_text,
    location_text,
    german_text,
    contract_text,
    warnings,
):
    label = (
        "STEPSTONE"
        if job["source"]
        == "stepstone"
        else "INDEED"
    )

    text = (
        f"🚨 NEW {label} JOB\n\n"
        f"💼 {details['title']}\n"
        f"🏢 {details['company'] or 'Not stated'}\n"
        f"📍 {details['location'] or 'Not stated'}\n"
        f"🏠 {location_text}\n"
        f"📅 Posted: {details['date_posted'] or 'Not stated'}\n"
        f"💼 Employment: {contract_text}\n\n"
        f"🎯 CV MATCH: {score}%\n"
        f"• Requirements: {breakdown.get('requirements', 0)}%\n"
        f"• Core requirements: {breakdown.get('core_requirements', 0)}%\n"
        f"• Responsibilities: {breakdown.get('responsibilities', 0)}%\n"
        f"• Role: {breakdown.get('role', 0)}%\n"
    )

    req_details = breakdown.get(
        "requirement_details",
        []
    )

    supported = [
        item
        for item in req_details
        if item.get(
            "weight",
            0,
        ) > 0
        and item.get(
            "score",
            0,
        ) >= 70
    ]

    gaps = [
        item
        for item in req_details
        if item.get(
            "weight",
            0,
        ) > 0
        and item.get(
            "score",
            0,
        ) < 70
    ]

    if supported:
        text += "\n✅ REQUIREMENTS SUPPORTED\n"

        for item in supported[:6]:
            text += (
                f"• {item['score']}% — "
                f"{item['text']}\n"
            )

    if gaps:
        text += "\n❌ REQUIREMENT GAPS\n"

        for item in gaps[:6]:
            text += (
                f"• {item['score']}% — "
                f"{item['text']}\n"
            )

    years = (
        "Not explicitly stated"
        if required_years is None
        else f"{required_years}+ years"
    )

    text += (
        "\n⏳ EXPERIENCE\n"
        f"• Arash: ~{ARASH_EXPERIENCE_YEARS:g} years\n"
        f"• Job asks: {years}\n"
        f"• Assessment: {experience_text}\n\n"
        "🌐 LANGUAGE\n"
        f"• German: {german_text}\n"
    )

    if warnings:
        text += "\n⚠️ WARNINGS\n"

        for warning in warnings[:8]:
            text += (
                f"• {warning}\n"
            )

    for heading, key in [
        (
            "📋 RESPONSIBILITIES",
            "tasks",
        ),
        (
            "🎓 REQUIREMENTS",
            "requirements",
        ),
    ]:
        values = details.get(
            key,
            []
        )

        if values:
            text += (
                "\n"
                + heading
                + "\n"
            )

            for value in values[:12]:
                text += (
                    f"• {value}\n"
                )

    text += (
        "\n🔗 OPEN / APPLY\n"
        + job["url"]
    )

    return text


def evaluate_job(job):
    if excluded_title(
        job.get(
            "title",
            "",
        )
    ):
        return

    if should_skip(
        job
    ):
        return

    details = get_details(
        job
    )

    if details is None:
        print(
            "Detail unavailable; not stored:",
            job["url"],
        )
        return

    if excluded_title(
        details["title"]
    ):
        remember(
            job,
            details,
            "rejected_title",
        )
        return

    age = age_days(
        details[
            "date_posted"
        ]
    )

    if (
        age is not None
        and age > MAX_AGE_DAYS
    ):
        remember(
            job,
            details,
            "rejected_age",
        )
        return

    location_ok, location_text = (
        location_status(
            details[
                "location"
            ],
            details[
                "description_text"
            ],
        )
    )

    if not location_ok:
        remember(
            job,
            details,
            "rejected_location",
        )
        return

    required_years = (
        extract_candidate_experience_years(
            details[
                "requirements"
            ],
            details[
                "description_text"
            ],
        )
    )

    reject_exp, exp_text = (
        experience_status(
            required_years
        )
    )

    if reject_exp:
        remember(
            job,
            details,
            "rejected_experience",
        )
        return

    reject_contract, contract_text = (
        contract_status(
            {
                "employment type":
                    details[
                        "employment_type"
                    ]
            },
            details[
                "description_text"
            ],
        )
    )

    if reject_contract:
        remember(
            job,
            details,
            "rejected_contract",
        )
        return

    reject_language, german_text, _ = (
        german_requirement(
            details[
                "description_text"
            ]
        )
    )

    if reject_language:
        remember(
            job,
            details,
            "rejected_language",
        )
        return

    score, matched, skill_warnings, breakdown = (
        evaluate_fit(
            details[
                "title"
            ],
            details[
                "description_text"
            ],
            details[
                "requirements"
            ],
            details[
                "tasks"
            ],
        )
    )

    if (
        not breakdown.get(
            "gates_pass",
            False,
        )
        or score < MIN_MATCH_PERCENT
    ):
        remember(
            job,
            details,
            "rejected_requirements",
            score,
        )
        return

    if (
        is_senior_title(
            details[
                "title"
            ]
        )
        and score < SENIOR_MIN_MATCH_PERCENT
    ):
        remember(
            job,
            details,
            "rejected_senior",
            score,
        )
        return

    warnings = []

    if german_text.startswith(
        "⚠️"
    ):
        warnings.append(
            german_text
        )

    warnings.extend(
        skill_warnings
    )

    warnings.extend(
        security_warnings(
            details[
                "description_text"
            ]
        )
    )

    message = build_message(
        job,
        details,
        score,
        breakdown,
        required_years,
        exp_text,
        location_text,
        german_text,
        contract_text,
        warnings,
    )

    print(
        "MATCH",
        job["source"],
        details["title"],
        score,
    )

    if send_long(
        message
    ):
        remember(
            job,
            details,
            "sent",
            score,
            True,
        )


def main():
    # Legacy collector is intentionally disabled. The market-radar workflow
    # is the only supported validation path for external job boards.
    if os.getenv("ENABLE_LEGACY_PUBLIC_SOURCES") != "1":
        print("Legacy StepStone/Indeed collector disabled; use market-radar workflow.")
        return
    print()
    print("=" * 70)
    print("ARASH PUBLIC JOB SOURCES - STEPSTONE + INDEED")
    print("=" * 70)

    if not RUN_EXTERNAL:
        print(
            "15-minute cadence: not due on this 5-minute scheduler tick."
        )
        return

    all_jobs = {}

    for query in QUERIES:
        print(
            "StepStone search:",
            query,
        )

        for job in stepstone_search(
            query
        ):
            all_jobs[
                (
                    job[
                        "source"
                    ],
                    job[
                        "job_id"
                    ],
                )
            ] = job

        print(
            "Indeed search:",
            query,
        )

        for job in indeed_search(
            query
        ):
            all_jobs[
                (
                    job[
                        "source"
                    ],
                    job[
                        "job_id"
                    ],
                )
            ] = job

    print(
        "Unique public-source jobs found:",
        len(all_jobs),
    )

    checked = 0

    for job in all_jobs.values():
        if checked >= 60:
            print(
                "Per-run detail cap reached; remaining jobs will be retried."
            )
            break

        if should_skip(
            job
        ):
            continue

        checked += 1

        print(
            "Checking:",
            job["source"],
            job.get(
                "title",
                "",
            ),
            job[
                "job_id"
            ],
        )

        evaluate_job(
            job
        )

        time.sleep(
            1.5
        )

    print(
        "Public-source new jobs checked:",
        checked,
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
