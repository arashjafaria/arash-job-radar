import json
import os
import html
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

from config import BOT_TOKEN, CHAT_ID

from profile import (
    ARASH_EXPERIENCE_YEARS,
    MUNICH_AREA,
    REMOTE_WORDS,
    EXCLUDE_WORDS,
    SKILLS,
    GOOD_ROLE_WORDS,
)


# ============================================================
# SETTINGS
# ============================================================

BMW_URL = (
    "https://jobs.bmwgroup.com/search/"
    "?q="
    "&sortColumn=referencedate"
    "&sortDirection=desc"
    "&searchResultView=LIST"
    "&locale=de_DE"
)

DATA_DIR = os.getenv("DATA_DIR", ".")

os.makedirs(
    DATA_DIR,
    exist_ok=True
)

SEEN_FILE = os.path.join(
    DATA_DIR,
    "bmw_seen_jobs.json"
)

PAGES_TO_SCAN = 5

MAX_JOB_AGE_DAYS = 3

MIN_MATCH_SCORE = 35

TELEGRAM_MAX = 3900


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(text):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": False
        },
        timeout=30
    )

    if response.status_code == 200:

        print(
            "Telegram message sent."
        )

        return True

    print(
        "Telegram error:",
        response.status_code,
        response.text
    )

    return False


def split_telegram_text(text):

    if len(text) <= TELEGRAM_MAX:

        return [text]

    chunks = []

    current = ""

    for line in text.splitlines():

        test = (
            current
            + line
            + "\n"
        )

        if len(test) > TELEGRAM_MAX:

            if current.strip():

                chunks.append(
                    current.strip()
                )

            current = (
                line
                + "\n"
            )

        else:

            current = test

    if current.strip():

        chunks.append(
            current.strip()
        )

    return chunks


def send_long_telegram(text):

    chunks = split_telegram_text(
        text
    )

    total = len(chunks)

    for index, chunk in enumerate(
        chunks,
        start=1
    ):

        if total > 1:

            chunk = (
                f"Part {index}/{total}\n\n"
                + chunk
            )

        send_telegram(
            chunk
        )


# ============================================================
# JOB MEMORY
# ============================================================

def load_seen_jobs():

    if not os.path.exists(
        SEEN_FILE
    ):

        return set()

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return set(
                json.load(file)
            )

    except Exception as e:

        print(
            "Seen database error:",
            e
        )

        return set()


def save_seen_jobs(seen_jobs):

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            sorted(
                list(seen_jobs)
            ),
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# LIST PAGE
# ============================================================

def read_current_page_jobs(
    page,
    page_number
):

    jobs = []

    links = page.locator(
        'a[href*="/job/"]'
    )

    count = links.count()

    print(
        f"Jobs visible on page {page_number}:",
        count
    )

    local_seen = set()

    for i in range(count):

        link = links.nth(i)

        try:

            href = (
                link.get_attribute(
                    "href"
                )
            )

            title = (
                link
                .inner_text()
                .strip()
            )

        except Exception:

            continue

        if not href or not title:

            continue

        full_url = urljoin(
            BMW_URL,
            href
        )

        full_url = html.unescape(
            full_url
        )

        if full_url in local_seen:

            continue

        local_seen.add(
            full_url
        )

        jobs.append({
            "title": title,
            "url": full_url
        })

    return jobs


def get_bmw_jobs():

    all_jobs = []

    global_seen = set()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1400,
                "height": 1000
            }
        )

        print(
            "Opening BMW Germany Jobs..."
        )

        page.goto(
            BMW_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(
            6000
        )

        print(
            "Page title:",
            page.title()
        )

        for page_number in range(
            1,
            PAGES_TO_SCAN + 1
        ):

            print()
            print("=" * 60)
            print(
                f"SCANNING BMW PAGE {page_number}"
            )
            print("=" * 60)

            if page_number > 1:

                aria_label = (
                    f"Zur Seite {page_number} wechseln"
                )

                button = page.locator(
                    f'button[aria-label="{aria_label}"]'
                )

                if button.count() == 0:

                    print(
                        "Pagination button not found."
                    )

                    break

                try:

                    button.click(
                        timeout=15000
                    )

                    page.wait_for_timeout(
                        3000
                    )

                except Exception as e:

                    print(
                        "Pagination error:",
                        e
                    )

                    break

            page_jobs = (
                read_current_page_jobs(
                    page,
                    page_number
                )
            )

            added = 0

            for job in page_jobs:

                if (
                    job["url"]
                    in global_seen
                ):

                    continue

                global_seen.add(
                    job["url"]
                )

                all_jobs.append(
                    job
                )

                added += 1

            print(
                "Unique jobs added:",
                added
            )

        browser.close()

    return all_jobs


# ============================================================
# JSON-LD SEARCH
# ============================================================

def find_job_posting(data):

    if isinstance(
        data,
        dict
    ):

        job_type = (
            data.get("@type")
        )

        if (
            job_type
            == "JobPosting"
        ):

            return data

        if isinstance(
            job_type,
            list
        ):

            if (
                "JobPosting"
                in job_type
            ):

                return data

        for value in data.values():

            result = (
                find_job_posting(
                    value
                )
            )

            if result:

                return result

    elif isinstance(
        data,
        list
    ):

        for item in data:

            result = (
                find_job_posting(
                    item
                )
            )

            if result:

                return result

    return None


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):

    text = html.unescape(
        str(text or "")
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def unique_items(items):

    result = []

    seen = set()

    for item in items:

        item = clean_text(
            item
        )

        if not item:

            continue

        key = item.lower()

        if key in seen:

            continue

        seen.add(
            key
        )

        result.append(
            item
        )

    return result


# ============================================================
# DESCRIPTION SECTION EXTRACTION
# ============================================================

TASK_HEADINGS = [
    "aufgaben",
    "deine aufgaben",
    "ihre aufgaben",
    "was erwartet dich",
    "was erwartet sie",
    "your responsibilities",
    "responsibilities",
    "what awaits you",
    "tätigkeiten",
]


REQUIREMENT_HEADINGS = [
    "qualifikation",
    "qualifikationen",
    "anforderungen",
    "dein profil",
    "ihr profil",
    "was bringst du mit",
    "was bringen sie mit",
    "what you should bring",
    "requirements",
    "qualifications",
    "your profile",
]


BENEFIT_HEADINGS = [
    "wir bieten",
    "benefits",
    "was bieten wir",
    "das bieten wir",
    "our benefits",
]


def classify_heading(
    heading
):

    h = (
        clean_text(heading)
        .lower()
    )

    for item in TASK_HEADINGS:

        if item in h:

            return "tasks"

    for item in REQUIREMENT_HEADINGS:

        if item in h:

            return "requirements"

    for item in BENEFIT_HEADINGS:

        if item in h:

            return "benefits"

    return "other"


def extract_description_sections(
    description_html
):

    soup = BeautifulSoup(
        description_html or "",
        "html.parser"
    )

    result = {
        "tasks": [],
        "requirements": [],
        "benefits": [],
        "other": [],
    }

    current_section = "other"

    for element in soup.find_all(
        [
            "h1",
            "h2",
            "h3",
            "h4",
            "strong",
            "p",
            "li"
        ]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True
            )
        )

        if not text:

            continue

        if element.name in [
            "h1",
            "h2",
            "h3",
            "h4"
        ]:

            current_section = (
                classify_heading(
                    text
                )
            )

            continue

        if (
            element.name == "strong"
            and len(text) < 100
        ):

            possible = (
                classify_heading(
                    text
                )
            )

            if possible != "other":

                current_section = (
                    possible
                )

                continue

        # Prefer list items, but also preserve useful paragraphs.
        if element.name == "li":

            result[
                current_section
            ].append(text)

        elif (
            element.name == "p"
            and len(text) >= 30
        ):

            result[
                current_section
            ].append(text)

    for key in result:

        result[key] = unique_items(
            result[key]
        )

    return result


# ============================================================
# LOCATION
# ============================================================

def build_location_text(
    posting
):

    locations = posting.get(
        "jobLocation",
        []
    )

    if isinstance(
        locations,
        dict
    ):

        locations = [
            locations
        ]

    output = []

    for location in locations:

        if not isinstance(
            location,
            dict
        ):

            continue

        address = location.get(
            "address",
            {}
        )

        if not isinstance(
            address,
            dict
        ):

            continue

        city = clean_text(
            address.get(
                "addressLocality",
                ""
            )
        )

        region = clean_text(
            address.get(
                "addressRegion",
                ""
            )
        )

        country = (
            address.get(
                "addressCountry",
                ""
            )
        )

        if isinstance(
            country,
            dict
        ):

            country = (
                country.get(
                    "name",
                    ""
                )
            )

        country = clean_text(
            country
        )

        pieces = [
            x
            for x in [
                city,
                region,
                country
            ]
            if x
        ]

        location_text = (
            ", ".join(
                pieces
            )
        )

        if (
            location_text
            and location_text
            not in output
        ):

            output.append(
                location_text
            )

    return " / ".join(
        output
    )


def location_match(
    location_text,
    full_text
):

    haystack = (
        (
            location_text
            + " "
            + full_text
        )
        .lower()
    )

    for city in MUNICH_AREA:

        if city in haystack:

            return (
                True,
                "Munich area"
            )

    for word in REMOTE_WORDS:

        if word in haystack:

            return (
                True,
                "Remote / hybrid"
            )

    return (
        False,
        "Outside preferred area"
    )


# ============================================================
# EXPERIENCE REQUIREMENT
# ============================================================

def extract_experience_years(
    text
):

    text_lower = (
        text.lower()
    )

    patterns = [
        r"(\d+)\s*\+?\s*(?:years|year)\s+(?:of\s+)?experience",
        r"at least\s+(\d+)\s+years",
        r"minimum\s+(\d+)\s+years",
        r"mindestens\s+(\d+)\s+jahre",
        r"min\.\s*(\d+)\s+jahre",
        r"(\d+)\s+jahre\s+berufserfahrung",
        r"(\d+)\s+jährige\s+berufserfahrung",
    ]

    years = []

    for pattern in patterns:

        for match in re.findall(
            pattern,
            text_lower
        ):

            try:

                years.append(
                    int(match)
                )

            except Exception:

                pass

    if not years:

        return None

    return max(
        years
    )


def experience_fit(
    required_years
):

    if required_years is None:

        return (
            "Not explicitly stated",
            5
        )

    if (
        required_years
        <= ARASH_EXPERIENCE_YEARS
    ):

        return (
            "Good fit",
            15
        )

    if (
        required_years
        <= ARASH_EXPERIENCE_YEARS
        + 1
    ):

        return (
            "Slight stretch",
            5
        )

    if required_years <= 4:

        return (
            "Stretch",
            -5
        )

    return (
        "Too senior",
        -20
    )


# ============================================================
# NEWNESS
# ============================================================

def parse_date(
    value
):

    if not value:

        return None

    value = clean_text(
        value
    )

    try:

        return (
            datetime
            .fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )
        )

    except Exception:

        pass

    try:

        return datetime.strptime(
            value[:10],
            "%Y-%m-%d"
        ).replace(
            tzinfo=timezone.utc
        )

    except Exception:

        return None


def job_age_days(
    date_posted
):

    dt = parse_date(
        date_posted
    )

    if dt is None:

        return None

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=timezone.utc
        )

    now = datetime.now(
        timezone.utc
    )

    delta = (
        now - dt
    )

    return max(
        0,
        delta.days
    )


# ============================================================
# MATCH SCORING
# ============================================================

def is_excluded(
    text
):

    low = text.lower()

    return any(
        word in low
        for word in EXCLUDE_WORDS
    )


def calculate_match(
    title,
    full_text,
    experience_adjustment
):

    title_low = (
        title.lower()
    )

    all_low = (
        (
            title
            + " "
            + full_text
        )
        .lower()
    )

    score = 0

    matched = []

    # Job title is especially important.
    for role in GOOD_ROLE_WORDS:

        if role in title_low:

            score += 12

            matched.append(
                role
            )

    for skill, points in SKILLS.items():

        if skill in all_low:

            # Skill in the title is more valuable.
            if skill in title_low:

                score += (
                    points + 5
                )

            else:

                score += points

            matched.append(
                skill
            )

    score += (
        experience_adjustment
    )

    return (
        score,
        unique_items(
            matched
        )
    )


# ============================================================
# FULL JOB DETAILS
# ============================================================

def get_job_details(
    job_url
):

    result = {
        "location": "",
        "date_posted": "",
        "employment_type": "",
        "description_text": "",
        "tasks": [],
        "requirements": [],
        "benefits": [],
        "other": [],
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/140 Safari/537.36"
        )
    }

    try:

        response = requests.get(
            job_url,
            headers=headers,
            timeout=30
        )

        if (
            response.status_code
            != 200
        ):

            print(
                "Detail HTTP status:",
                response.status_code
            )

            return result

        page_soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        scripts = (
            page_soup.find_all(
                "script",
                attrs={
                    "type":
                    "application/ld+json"
                }
            )
        )

        for script in scripts:

            raw = script.string

            if not raw:

                continue

            try:

                data = json.loads(
                    raw
                )

            except Exception:

                continue

            posting = (
                find_job_posting(
                    data
                )
            )

            if not posting:

                continue

            result[
                "date_posted"
            ] = clean_text(
                posting.get(
                    "datePosted",
                    ""
                )
            )

            employment = (
                posting.get(
                    "employmentType",
                    ""
                )
            )

            if isinstance(
                employment,
                list
            ):

                employment = (
                    ", ".join(
                        employment
                    )
                )

            result[
                "employment_type"
            ] = clean_text(
                employment
            )

            result[
                "location"
            ] = (
                build_location_text(
                    posting
                )
            )

            description_html = (
                posting.get(
                    "description",
                    ""
                )
            )

            description_soup = (
                BeautifulSoup(
                    description_html,
                    "html.parser"
                )
            )

            result[
                "description_text"
            ] = clean_text(
                description_soup.get_text(
                    " ",
                    strip=True
                )
            )

            sections = (
                extract_description_sections(
                    description_html
                )
            )

            result.update(
                sections
            )

            return result

    except Exception as e:

        print(
            "Job detail error:",
            e
        )

    return result


# ============================================================
# TELEGRAM FORMATTING
# ============================================================

def bullet_section(
    title,
    items
):

    if not items:

        return ""

    text = (
        f"\n{title}\n"
    )

    for item in items:

        text += (
            f"• {item}\n"
        )

    return text


def build_telegram_message(
    job,
    details,
    score,
    matched,
    location_status,
    required_years,
    experience_status
):

    date_posted = (
        details[
            "date_posted"
        ]
        or "Not detected"
    )

    employment = (
        details[
            "employment_type"
        ]
        or "Not detected"
    )

    location = (
        details[
            "location"
        ]
        or location_status
    )

    if required_years is None:

        exp_requirement = (
            "Not explicitly stated"
        )

    else:

        exp_requirement = (
            f"{required_years}+ years"
        )

    message = (
        "🚨 NEW BMW JOB\n\n"

        f"💼 {job['title']}\n"

        "🏢 BMW Group\n"

        f"📍 {location}\n"

        f"🏠 Location fit: "
        f"{location_status}\n"

        f"📅 Posted: "
        f"{date_posted}\n"

        f"🧑‍💼 Type: "
        f"{employment}\n\n"

        f"🎯 Match score: "
        f"{score}\n"

        f"✅ Matching areas: "
        f"{', '.join(matched)}\n\n"

        "⏳ EXPERIENCE\n"

        f"• Arash: ~"
        f"{ARASH_EXPERIENCE_YEARS:g} years professional experience\n"

        f"• Job asks: "
        f"{exp_requirement}\n"

        f"• Assessment: "
        f"{experience_status}\n"
    )

    message += bullet_section(
        "📌 RESPONSIBILITIES",
        details[
            "tasks"
        ]
    )

    message += bullet_section(
        "🎓 REQUIREMENTS",
        details[
            "requirements"
        ]
    )

    message += bullet_section(
        "🎁 BENEFITS / OTHER INFO",
        details[
            "benefits"
        ]
    )

    # If BMW's page doesn't use recognizable section headings,
    # preserve remaining details instead of losing them.
    if (
        not details[
            "tasks"
        ]
        and not details[
            "requirements"
        ]
    ):

        message += bullet_section(
            "📄 JOB DETAILS",
            details[
                "other"
            ]
        )

    message += (
        "\n🔗 APPLY / FULL JOB\n"
        f"{job['url']}"
    )

    return message


# ============================================================
# MAIN
# ============================================================

print()
print("=" * 70)
print("ARASH JOB RADAR - BMW ADVANCED")
print("=" * 70)

jobs = get_bmw_jobs()

print()
print(
    "TOTAL BMW JOBS READ:",
    len(jobs)
)

seen_jobs = load_seen_jobs()

new_jobs = []

for job in jobs:

    if (
        job["url"]
        not in seen_jobs
    ):

        new_jobs.append(
            job
        )

        # Mark as seen even if later rejected.
        seen_jobs.add(
            job["url"]
        )

print()
print(
    "NEW BMW JOBS:",
    len(new_jobs)
)

sent_count = 0

for job in new_jobs:

    print()
    print("-" * 70)

    print(
        "Checking:",
        job["title"]
    )

    if is_excluded(
        job["title"]
    ):

        print(
            "Rejected: student/internship/apprenticeship"
        )

        continue

    details = get_job_details(
        job["url"]
    )

    full_text = (
        job["title"]
        + " "
        + details[
            "description_text"
        ]
    )

    if is_excluded(
        full_text
    ):

        print(
            "Rejected by description."
        )

        continue

    # --------------------------------------------------------
    # NEWNESS
    # --------------------------------------------------------

    age = job_age_days(
        details[
            "date_posted"
        ]
    )

    if (
        age is not None
        and age
        > MAX_JOB_AGE_DAYS
    ):

        print(
            f"Rejected: {age} days old."
        )

        continue

    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    location_ok, location_status = (
        location_match(
            details[
                "location"
            ],
            full_text
        )
    )

    if not location_ok:

        print(
            "Rejected:",
            location_status,
            details[
                "location"
            ]
        )

        continue

    # --------------------------------------------------------
    # EXPERIENCE
    # --------------------------------------------------------

    required_years = (
        extract_experience_years(
            full_text
        )
    )

    experience_status, exp_adjust = (
        experience_fit(
            required_years
        )
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score, matched = (
        calculate_match(
            job["title"],
            full_text,
            exp_adjust
        )
    )

    print(
        "Match score:",
        score
    )

    print(
        "Experience:",
        experience_status
    )

    if score < MIN_MATCH_SCORE:

        print(
            "Rejected: score too low."
        )

        continue

    # Very senior jobs need an exceptionally strong skill match.
    if (
        experience_status
        == "Too senior"
        and score < 80
    ):

        print(
            "Rejected: too senior."
        )

        continue

    message = (
        build_telegram_message(
            job,
            details,
            score,
            matched,
            location_status,
            required_years,
            experience_status
        )
    )

    print(
        "MATCH -> Telegram"
    )

    send_long_telegram(
        message
    )

    sent_count += 1


save_seen_jobs(
    seen_jobs
)

print()
print("=" * 70)

print(
    "Relevant jobs sent:",
    sent_count
)

print("=" * 70)
print("BMW scan finished.")
print("=" * 70)