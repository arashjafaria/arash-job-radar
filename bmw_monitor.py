import json
import os
import html
import re
import requests

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

from config import BOT_TOKEN, CHAT_ID


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

os.makedirs(DATA_DIR, exist_ok=True)

SEEN_FILE = os.path.join(
    DATA_DIR,
    "bmw_seen_jobs.json"
)

# Read first 5 BMW pages = about 50 newest jobs
PAGES_TO_SCAN = 5

# Minimum score needed to send Telegram alert
MIN_MATCH_SCORE = 30


# ============================================================
# JOBS WE NEVER WANT
# ============================================================

EXCLUDE_PATTERNS = [
    r"\bpraktikant",
    r"\bpraktikum",
    r"\bwerkstudent",
    r"\bwerkstudentin",
    r"\bazubi\b",
    r"\bauszubild",
    r"\bausbildung\b",
    r"\bduales studium\b",
    r"\bdualer student\b",
    r"\bstudienabschlussarbeit\b",
    r"\babschlussarbeit\b",
    r"\bmasterarbeit\b",
    r"\bbachelorarbeit\b",
    r"\bthesis\b",
    r"\bdoktorand",
    r"\bpromotion\b",
    r"\btrainee\b",
    r"\bschüler",
]


# ============================================================
# MATCH SCORE
# ============================================================

SCORE_PATTERNS = [

    # Very strong matches
    (r"\bcanoe\b", 40, "CANoe"),
    (r"\bcapl\b", 40, "CAPL"),
    (r"\buds\b", 40, "UDS"),

    (r"\bhil\b", 35, "HIL"),
    (r"\bsil\b", 35, "SIL"),

    (r"\btestingenieur", 35, "Test Engineer"),
    (r"\btest engineer", 35, "Test Engineer"),

    (r"\bdiagnos", 30, "Diagnostics"),

    (r"\bintegration", 30, "Integration"),

    (r"\bvalidation", 30, "Validation"),
    (r"\bverification", 30, "Verification"),

    (r"\becu\b", 30, "ECU"),
    (r"\bsteuergerät", 30, "ECU"),

    (r"\bradar\b", 30, "Radar"),
    (r"\badas\b", 30, "ADAS"),

    # Good matches
    (r"\btest\b", 25, "Testing"),
    (r"\btesting\b", 25, "Testing"),

    (r"\bembedded\b", 25, "Embedded"),

    (r"\bpython\b", 25, "Python"),

    (r"\bautomatisierung", 25, "Automation"),
    (r"\bautomation\b", 25, "Automation"),

    (r"\bethernet\b", 25, "Automotive Ethernet"),

    (r"\bcan fd\b", 25, "CAN FD"),
    (r"\bcan-fd\b", 25, "CAN FD"),

    # Medium matches
    (r"\bsoftware\b", 15, "Software"),

    (r"\bentwicklungsingenieur", 15, "Development Engineer"),
    (r"\bdevelopment engineer", 15, "Development Engineer"),

    (r"\bsystemingenieur", 15, "System Engineer"),
    (r"\bsystem engineer", 15, "System Engineer"),

    (r"\bsoftwareentwickler", 15, "Software Developer"),

    (r"\be/e\b", 15, "E/E"),

    # Vehicle alone must NOT be enough
    (r"\bfahrzeug", 5, "Automotive"),
    (r"\bvehicle\b", 5, "Automotive"),
]


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    telegram_url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": False
    }

    try:

        response = requests.post(
            telegram_url,
            data=data,
            timeout=20
        )

        if response.status_code == 200:
            print("Telegram message sent successfully.")

        else:
            print("Telegram ERROR:")
            print(response.status_code)
            print(response.text)

    except Exception as e:

        print("Telegram connection error:")
        print(e)


# ============================================================
# CHECK IF JOB MUST BE EXCLUDED
# ============================================================

def is_excluded(title):

    title_lower = title.lower()

    for pattern in EXCLUDE_PATTERNS:

        if re.search(
            pattern,
            title_lower,
            flags=re.IGNORECASE
        ):
            return True

    return False


# ============================================================
# CALCULATE MATCH SCORE
# ============================================================

def calculate_match(title):

    title_lower = title.lower()

    score = 0
    matches = []

    for pattern, points, label in SCORE_PATTERNS:

        if re.search(
            pattern,
            title_lower,
            flags=re.IGNORECASE
        ):

            score += points

            if label not in matches:
                matches.append(label)

    return score, matches


# ============================================================
# LOAD SEEN JOBS
# ============================================================

def load_seen_jobs():

    if not os.path.exists(SEEN_FILE):
        return set()

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

            return set(data)

    except Exception as e:

        print("Could not load seen jobs:")
        print(e)

        return set()


# ============================================================
# SAVE SEEN JOBS
# ============================================================

def save_seen_jobs(seen_jobs):

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            sorted(list(seen_jobs)),
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# READ JOBS FROM CURRENT BMW PAGE
# ============================================================

def read_current_page_jobs(page, page_number):

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

            href = link.get_attribute("href")

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


# ============================================================
# GET BMW JOBS WITH REAL PAGINATION
# ============================================================

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

        print("Opening BMW Germany Jobs...")

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

            # Page 1 is already open
            # For pages 2-5 click BMW pagination button

            if page_number > 1:

                aria_label = (
                    f"Zur Seite {page_number} wechseln"
                )

                button = page.locator(
                    f'button[aria-label="{aria_label}"]'
                )

                if button.count() == 0:

                    print(
                        f"Page {page_number} button not found."
                    )

                    break

                print(
                    f"Clicking BMW page {page_number}..."
                )

                try:

                    button.click(
                        timeout=15000
                    )

                    page.wait_for_timeout(
                        3000
                    )

                except Exception as e:

                    print("Page click error:")
                    print(e)

                    break

            page_jobs = read_current_page_jobs(
                page,
                page_number
            )

            added = 0

            for job in page_jobs:

                if job["url"] in global_seen:
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
# FIND JOBPOSTING JSON-LD
# ============================================================

def find_job_posting(data):

    if isinstance(data, dict):

        job_type = data.get("@type")

        if job_type == "JobPosting":
            return data

        if isinstance(job_type, list):

            if "JobPosting" in job_type:
                return data

        for value in data.values():

            result = find_job_posting(
                value
            )

            if result:
                return result

    elif isinstance(data, list):

        for item in data:

            result = find_job_posting(
                item
            )

            if result:
                return result

    return None


# ============================================================
# READ JOB DETAILS
# ============================================================

def get_job_details(job_url):

    details = {
        "location": "",
        "date_posted": "",
        "employment_type": ""
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
            timeout=20
        )

        if response.status_code != 200:

            print(
                "Job detail page status:",
                response.status_code
            )

            return details

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        scripts = soup.find_all(
            "script",
            attrs={
                "type": "application/ld+json"
            }
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

            posting = find_job_posting(
                data
            )

            if not posting:
                continue


            # DATE POSTED

            details["date_posted"] = (
                posting.get(
                    "datePosted",
                    ""
                )
            )


            # EMPLOYMENT TYPE

            employment = posting.get(
                "employmentType",
                ""
            )

            if isinstance(
                employment,
                list
            ):

                employment = ", ".join(
                    employment
                )

            if employment:

                details["employment_type"] = str(
                    employment
                )


            # LOCATION

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

            location_parts = []

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

                city = address.get(
                    "addressLocality",
                    ""
                )

                region = address.get(
                    "addressRegion",
                    ""
                )

                country = address.get(
                    "addressCountry",
                    ""
                )

                if isinstance(
                    country,
                    dict
                ):

                    country = country.get(
                        "name",
                        ""
                    )

                pieces = []

                if city:
                    pieces.append(
                        str(city)
                    )

                if region:
                    pieces.append(
                        str(region)
                    )

                if country:
                    pieces.append(
                        str(country)
                    )

                location_text = ", ".join(
                    pieces
                )

                if (
                    location_text
                    and location_text not in location_parts
                ):

                    location_parts.append(
                        location_text
                    )

            details["location"] = " / ".join(
                location_parts
            )

            return details

    except Exception as e:

        print(
            "Could not read job details:"
        )

        print(e)

    return details


# ============================================================
# MAIN
# ============================================================

print()
print("=" * 70)
print("ARASH JOB RADAR - BMW")
print("=" * 70)


# Check whether this is the first ever run
first_run = not os.path.exists(SEEN_FILE)


jobs = get_bmw_jobs()


print()
print("=" * 70)

print(
    "TOTAL UNIQUE BMW JOBS READ:",
    len(jobs)
)

print("=" * 70)


seen_jobs = load_seen_jobs()


# ============================================================
# FIRST RUN
# ============================================================

if first_run:

    print()
    print("FIRST RUN")
    print(
        "Saving current BMW jobs as baseline."
    )
    print(
        "No Telegram alerts will be sent."
    )

    for job in jobs:

        seen_jobs.add(
            job["url"]
        )

    save_seen_jobs(
        seen_jobs
    )

    print()
    print(
        "Baseline saved:",
        len(seen_jobs),
        "jobs"
    )

    print()
    print("=" * 70)
    print("BMW scan finished.")
    print("=" * 70)

    raise SystemExit


# ============================================================
# FIND NEW JOBS
# ============================================================

new_jobs = []


for job in jobs:

    if job["url"] not in seen_jobs:

        new_jobs.append(
            job
        )

        seen_jobs.add(
            job["url"]
        )


print()
print(
    "New BMW jobs detected:",
    len(new_jobs)
)


sent_count = 0


# ============================================================
# ANALYZE NEW JOBS
# ============================================================

for job in new_jobs:

    title = job["title"]
    job_url = job["url"]

    print()
    print("-" * 70)

    print("NEW JOB:")
    print(title)


    # --------------------------------------------------------
    # EXCLUSION
    # --------------------------------------------------------

    if is_excluded(title):

        print(
            "EXCLUDED -> internship / student / apprenticeship"
        )

        continue


    # --------------------------------------------------------
    # MATCH SCORE
    # --------------------------------------------------------

    score, matches = calculate_match(
        title
    )

    print(
        "Match score:",
        score
    )

    if matches:

        print(
            "Matched:",
            ", ".join(matches)
        )


    # --------------------------------------------------------
    # IGNORE LOW SCORE JOB
    # --------------------------------------------------------

    if score < MIN_MATCH_SCORE:

        print(
            "Score too low -> ignored"
        )

        continue


    # --------------------------------------------------------
    # LOAD DETAILS
    # --------------------------------------------------------

    print(
        "Relevant job -> reading details..."
    )

    details = get_job_details(
        job_url
    )


    location = (
        details["location"]
        or "Location not detected"
    )

    date_posted = (
        details["date_posted"]
        or "Not detected"
    )

    employment_type = (
        details["employment_type"]
        or "Not detected"
    )


    matched_text = ", ".join(
        matches
    )


    # --------------------------------------------------------
    # TELEGRAM MESSAGE
    # --------------------------------------------------------

    message = (
        "🚨 NEW BMW JOB\n\n"

        f"💼 {title}\n\n"

        "🏢 BMW Group\n"

        f"📍 {location}\n"

        f"📅 Posted: {date_posted}\n"

        f"🧑‍💼 Type: {employment_type}\n\n"

        f"🎯 Match score: {score}\n"

        f"✅ Match: {matched_text}\n\n"

        f"🔗 {job_url}\n\n"

        "#BMW #Automotive #JobRadar"
    )


    print(
        "MATCH -> Sending Telegram alert"
    )


    send_telegram(
        message
    )


    sent_count += 1


# ============================================================
# SAVE DATABASE
# ============================================================

save_seen_jobs(
    seen_jobs
)


print()
print("=" * 70)

print(
    "Relevant new jobs sent:",
    sent_count
)

print("=" * 70)

print(
    "BMW scan finished."
)

print("=" * 70)