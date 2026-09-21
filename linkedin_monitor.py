import os
import re
import time
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from config import BOT_TOKEN, CHAT_ID

from profile import (
    ARASH_EXPERIENCE_YEARS,
    MUNICH_AREA,
    REMOTE_WORDS,
    EXCLUDE_WORDS,
)

from supabase_store import (
    job_exists,
    save_job,
)


# ============================================================
# ARASH JOB RADAR - LINKEDIN V5 + SUPABASE
# ============================================================

VERSION = "V5 + SUPABASE"
SOURCE = "linkedin"


SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/"
    "jobs/api/seeMoreJobPostings/search"
)

DETAIL_URL = (
    "https://www.linkedin.com/jobs-guest/"
    "jobs/api/jobPosting/{}"
)


# ============================================================
# SEARCH SETTINGS
# ============================================================

SEARCH_QUERIES = [
    "Automotive Test Engineer",
    "System Integration Engineer Automotive",
    "ECU Test Engineer Automotive",
    "Automotive Diagnostics Engineer",
    "ADAS HIL Test Engineer",
]

LOCATION_QUERY = "Germany"

# Last 24 hours
FRESH_SECONDS = 86400

MIN_MATCH_SCORE = 45

SEARCH_DELAY_SECONDS = 2.5
DETAIL_DELAY_SECONDS = 2.5

TELEGRAM_LIMIT = 3900


TEST_MODE = (
    os.getenv(
        "LINKEDIN_TEST_MODE",
        "0"
    )
    == "1"
)


# ============================================================
# REQUEST SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),

    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),

    "Accept-Language":
        "en-US,en;q=0.9,de;q=0.8",
})


# ============================================================
# ARASH CORE SKILLS
# ============================================================

CORE_SKILLS = {

    "ecu-test": 22,
    "ecu test": 22,

    "canoe": 22,

    "uds": 22,

    "ecu diagnostics": 22,

    "diagnostic": 18,
    "diagnostics": 18,
    "diagnose": 18,

    "dtc": 18,
    "did": 18,

    "can fd": 20,
    "can-fd": 20,

    "system testing": 20,
    "system test": 20,

    "system integration testing": 22,
    "integration testing": 20,

    "hil": 18,
    "sil": 18,

    "adas": 20,

    "radar": 20,

    "usrr": 22,

    "vehicle integration": 18,

    "fahrzeugintegration": 18,

    "automotive ethernet": 20,

    "doip": 18,

    "some/ip": 16,

    "dlt": 14,
}


# ============================================================
# SUPPORT SKILLS
# ============================================================

SUPPORT_SKILLS = {

    "requirements-based testing": 16,

    "regression testing": 16,

    "test automation": 16,

    "testautomatisierung": 16,

    "python": 14,

    "root cause": 12,

    "root-cause": 12,

    "validation": 12,

    "verification": 12,

    "embedded": 7,

    "codebeamer": 8,

    "octane": 8,

    "jira": 5,

    "github": 5,

    "wireshark": 6,

    "carmen": 8,

    "e-sys": 8,

    "esys": 8,

    "ediabas": 7,

    # Basic according to current CV
    "capl": 5,

    # Basic according to current CV
    "c++": 0,
}


# ============================================================
# ROLE WORDS
# ============================================================

ROLE_WORDS = [

    "automotive test engineer",

    "test engineer",

    "testingenieur",

    "system test engineer",

    "system integration engineer",

    "integration engineer",

    "integrationsingenieur",

    "vehicle integration engineer",

    "fahrzeugintegration",

    "validation engineer",

    "verification engineer",

    "diagnostics engineer",

    "diagnostic engineer",

    "hil test engineer",

    "sil test engineer",

    "adas test engineer",

    "radar test engineer",

    "test automation engineer",
]


# ============================================================
# AUTOMOTIVE DOMAIN
# ============================================================

AUTOMOTIVE_DOMAIN_WORDS = [

    "automotive",

    "vehicle",

    "fahrzeug",

    "ecu",

    "steuergerät",

    "can fd",

    "can-fd",

    "uds",

    "adas",

    "radar",

    "usrr",

    "mrr",

    "srr",

    "automotive ethernet",

    "doip",

    "some/ip",

    "ecu-test",

    "ecu test",

    "canoe",
]


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean(text):

    return re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()


def clean_url(url):

    if not url:

        return ""


    try:

        parts = urlsplit(
            url
        )

        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                "",
                "",
            )
        )

    except Exception:

        return url


# ============================================================
# SAFE TERM MATCHING
# ============================================================

def term_present(
    term,
    text
):

    if not term or not text:

        return False


    escaped = re.escape(
        term.strip()
    )


    pattern = (
        r"(?<![A-Za-z0-9])"
        + escaped
        + r"(?![A-Za-z0-9])"
    )


    return bool(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )
    )


def any_term_present(
    terms,
    text
):

    return any(
        term_present(
            term,
            text
        )
        for term in terms
    )


# ============================================================
# SUPABASE MEMORY
# ============================================================

def already_seen(job_id):

    if TEST_MODE:

        return False


    try:

        return job_exists(
            SOURCE,
            str(job_id)
        )

    except Exception as exc:

        print(
            "Supabase lookup error:",
            exc
        )

        # Do not silently lose the job.
        raise


def remember_job(
    job,
    status,
    match_score=None,
    sent_to_telegram=False,
):

    if TEST_MODE:

        return True


    try:

        inserted = save_job(

            source=SOURCE,

            job_id=str(
                job["job_id"]
            ),

            title=job.get(
                "title",
                ""
            ),

            company=job.get(
                "company",
                ""
            ),

            location=job.get(
                "location",
                ""
            ),

            url=job.get(
                "url",
                ""
            ),

            posted_at=job.get(
                "posted",
                ""
            ),

            match_score=match_score,

            status=status,

            sent_to_telegram=(
                sent_to_telegram
            ),
        )


        if inserted:

            print(
                "Saved to Supabase:",
                status
            )

        else:

            print(
                "Already stored in Supabase."
            )


        return True


    except Exception as exc:

        print(
            "SUPABASE SAVE ERROR:",
            exc
        )

        return False


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(text):

    if TEST_MODE:

        print(
            "TEST MODE: Telegram suppressed."
        )

        return True


    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )


    try:

        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": False,
            },
            timeout=20,
        )

    except Exception as exc:

        print(
            "Telegram request error:",
            exc
        )

        return False


    print(
        "Telegram:",
        response.status_code
    )


    return (
        response.status_code
        == 200
    )


def send_long_message(text):

    if len(text) <= TELEGRAM_LIMIT:

        return send_telegram(
            text
        )


    chunks = []

    current = ""


    for line in text.splitlines():

        candidate = (
            current
            + line
            + "\n"
        )


        if len(candidate) > TELEGRAM_LIMIT:

            if current.strip():

                chunks.append(
                    current.strip()
                )

            current = (
                line
                + "\n"
            )

        else:

            current = candidate


    if current.strip():

        chunks.append(
            current.strip()
        )


    success = True


    for index, chunk in enumerate(
        chunks,
        start=1
    ):

        if not send_telegram(
            f"Part {index}/{len(chunks)}\n\n"
            + chunk
        ):

            success = False


        if not TEST_MODE:

            time.sleep(0.7)


    return success


# ============================================================
# TITLE FILTER
# ============================================================

def title_is_excluded(title):

    low = (
        title
        or ""
    ).lower()


    return any(
        word.lower() in low
        for word in EXCLUDE_WORDS
    )


# ============================================================
# EMPLOYMENT TYPE FILTER
# ============================================================

def employment_type_status(
    criteria
):

    employment_value = ""


    for key, value in criteria.items():

        key_low = (
            key.lower()
        )


        if any(
            item in key_low
            for item in [
                "employment type",
                "beschäftigungsart",
                "anstellungsart",
                "employment",
            ]
        ):

            employment_value = (
                value.lower()
            )

            break


    if not employment_value:

        return (
            False,
            "Not stated"
        )


    excluded = [

        "internship",

        "intern",

        "praktikum",

        "working student",

        "werkstudent",

        "apprenticeship",

        "ausbildung",

        "trainee",

        "part-time",

        "part time",

        "teilzeit",
    ]


    for item in excluded:

        if item in employment_value:

            return (
                True,
                employment_value
            )


    return (
        False,
        employment_value
    )


# ============================================================
# LOCATION PRE-CHECK
# ============================================================

def location_precheck(
    location
):

    low = (
        location
        or ""
    ).lower().strip()


    for city in MUNICH_AREA:

        if city.lower() in low:

            return (
                True,
                "Munich area"
            )


    if any(
        term in low
        for term in [
            "remote",
            "home office",
            "homeoffice",
        ]
    ):

        return (
            True,
            "Possible remote"
        )


    generic_locations = [

        "germany",

        "deutschland",

        "germany remote",

        "remote germany",

        "bavaria, germany",

        "bayern, deutschland",
    ]


    if low in generic_locations:

        return (
            True,
            "Generic Germany/Bavaria location"
        )


    return (
        False,
        "Specific location outside Munich area"
    )


# ============================================================
# FINAL LOCATION CHECK
# ============================================================

def final_location_check(
    location,
    description
):

    location_low = (
        location
        or ""
    ).lower()


    full_text = (
        (location or "")
        + " "
        + (description or "")
    ).lower()


    for city in MUNICH_AREA:

        if city.lower() in location_low:

            return (
                True,
                "Munich area"
            )


    negative_remote = [

        "no remote",

        "not remote",

        "remote work is not",

        "remote work not",

        "kein homeoffice",

        "keine homeoffice",

        "kein remote",

        "nicht remote",
    ]


    if any(
        phrase in full_text
        for phrase in negative_remote
    ):

        return (
            False,
            "Remote explicitly unavailable"
        )


    remote_found = any(
        word.lower() in full_text
        for word in REMOTE_WORDS
    )


    germany_context = any(
        term in full_text
        for term in [
            "germany",
            "deutschland",
            "bundesweit",
        ]
    )


    if (
        remote_found
        and germany_context
    ):

        return (
            True,
            "Remote Germany"
        )


    return (
        False,
        "Outside Munich area / not Germany remote"
    )


# ============================================================
# AUTOMOTIVE CHECK
# ============================================================

def has_automotive_context(
    text
):

    return any_term_present(
        AUTOMOTIVE_DOMAIN_WORDS,
        text
    )


# ============================================================
# EXPERIENCE
# ============================================================

def extract_experience_years(
    text
):

    low = (
        text
        or ""
    ).lower()


    patterns = [

        r"(\d+)\s*\+?\s*years?"
        r"\s+(?:of\s+)?experience",

        r"at least\s+(\d+)"
        r"\s+years?",

        r"minimum\s+(\d+)"
        r"\s+years?",

        r"minimum of\s+(\d+)"
        r"\s+years?",

        r"mindestens\s+(\d+)"
        r"\s+jahre",

        r"(\d+)\s+jahre"
        r"\s+berufserfahrung",
    ]


    values = []


    for pattern in patterns:

        for value in re.findall(
            pattern,
            low
        ):

            try:

                values.append(
                    int(value)
                )

            except Exception:

                pass


    if not values:

        return None


    return max(
        values
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


    if required_years <= 3:

        return (
            "Slight stretch",
            7
        )


    if required_years <= 4:

        return (
            "Stretch",
            -8
        )


    return (
        "Too senior",
        -25
    )


# ============================================================
# GERMAN REQUIREMENT
# ============================================================

def german_requirement(
    text
):

    low = (
        text
        or ""
    ).lower()


    hard_patterns = [

        r"german.{0,40}\bc1\b",

        r"deutsch.{0,40}\bc1\b",

        r"\bc1\b.{0,40}german",

        r"\bc1\b.{0,40}deutsch",

        r"german.{0,40}\bc2\b",

        r"deutsch.{0,40}\bc2\b",

        r"native german",

        r"german native",

        r"deutsch.{0,40}muttersprache",

        r"muttersprache.{0,40}deutsch",

        r"verhandlungssicher.{0,40}deutsch",

        r"deutsch.{0,40}verhandlungssicher",

        r"fluent.{0,30}german",

        r"german.{0,30}fluent",

        r"fluent in german",

        r"fließend.{0,30}deutsch",

        r"fliessend.{0,30}deutsch",

        r"sehr gute deutschkenntnisse",
    ]


    for pattern in hard_patterns:

        if re.search(
            pattern,
            low
        ):

            return (
                "German requirement above current B1",
                -100,
                True
            )


    b2_patterns = [

        r"german.{0,40}\bb2\b",

        r"deutsch.{0,40}\bb2\b",

        r"\bb2\b.{0,40}german",

        r"\bb2\b.{0,40}deutsch",
    ]


    for pattern in b2_patterns:

        if re.search(
            pattern,
            low
        ):

            return (
                "German B2 requested",
                -12,
                False
            )


    return (
        "No strong German requirement detected",
        0,
        False
    )


# ============================================================
# C++ REQUIREMENT
# ============================================================

def cpp_requirement(
    text
):

    low = (
        text
        or ""
    ).lower()


    patterns = [

        r"strong.{0,30}c\+\+",

        r"excellent.{0,30}c\+\+",

        r"proficient.{0,30}c\+\+",

        r"advanced.{0,30}c\+\+",

        r"expert.{0,30}c\+\+",

        r"sehr gute.{0,30}c\+\+",

        r"fundierte.{0,30}c\+\+",

        r"umfangreiche.{0,30}c\+\+",
    ]


    for pattern in patterns:

        if re.search(
            pattern,
            low
        ):

            return (
                "Strong C++ requested",
                -15
            )


    return (
        "No strong C++ requirement detected",
        0
    )


# ============================================================
# MATCH SCORE
# ============================================================

def calculate_score(
    title,
    description,
    experience_adjustment,
    language_adjustment,
    cpp_adjustment,
):

    full_text = (
        (title or "")
        + " "
        + (description or "")
    )


    score = 0

    matched = []

    core_matches = []


    for role in ROLE_WORDS:

        if term_present(
            role,
            title
        ):

            score += 15

            matched.append(
                role
            )


    for skill, points in CORE_SKILLS.items():

        if term_present(
            skill,
            full_text
        ):

            bonus = (
                5
                if term_present(
                    skill,
                    title
                )
                else 0
            )


            score += (
                points
                + bonus
            )


            matched.append(
                skill
            )

            core_matches.append(
                skill
            )


    for skill, points in SUPPORT_SKILLS.items():

        if term_present(
            skill,
            full_text
        ):

            bonus = (
                3
                if term_present(
                    skill,
                    title
                )
                else 0
            )


            score += (
                points
                + bonus
            )


            matched.append(
                skill
            )


    score += (
        experience_adjustment
    )

    score += (
        language_adjustment
    )

    score += (
        cpp_adjustment
    )


    matched = list(
        dict.fromkeys(
            matched
        )
    )


    core_matches = list(
        dict.fromkeys(
            core_matches
        )
    )


    return (
        score,
        matched,
        core_matches
    )


# ============================================================
# JOB ID
# ============================================================

def extract_job_id_from_card(
    card
):

    holder = card.select_one(
        "[data-entity-urn]"
    )


    urn = ""


    if holder:

        urn = holder.get(
            "data-entity-urn",
            ""
        )


    if not urn:

        urn = card.get(
            "data-entity-urn",
            ""
        )


    match = re.search(
        r"jobPosting:(\d+)",
        urn
    )


    if match:

        return match.group(1)


    link = card.select_one(
        "a.base-card__full-link"
    )


    if not link:

        return None


    href = link.get(
        "href",
        ""
    )


    patterns = [

        r"currentJobId=(\d+)",

        r"/jobs/view/"
        r"[^/?]*?(\d{8,})",
    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            href
        )


        if match:

            return match.group(1)


    return None


# ============================================================
# LINKEDIN SEARCH
# ============================================================

def search_linkedin_jobs(
    keyword
):

    params = {

        "keywords":
            keyword,

        "location":
            LOCATION_QUERY,

        "f_TPR":
            f"r{FRESH_SECONDS}",

        "sortBy":
            "DD",

        "start":
            0,
    }


    url = (
        SEARCH_URL
        + "?"
        + urlencode(
            params
        )
    )


    try:

        response = SESSION.get(
            url,
            timeout=12
        )

    except Exception as exc:

        print(
            "  Search error:",
            exc
        )

        return []


    print(
        "  HTTP:",
        response.status_code,
        "| bytes:",
        len(response.text)
    )


    if response.status_code == 429:

        print(
            "  LinkedIn rate limit."
        )

        return []


    if response.status_code != 200:

        return []


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    jobs = []


    for card in soup.select(
        "li"
    ):

        job_id = (
            extract_job_id_from_card(
                card
            )
        )


        if not job_id:

            continue


        title_el = card.select_one(
            ".base-search-card__title"
        )

        company_el = card.select_one(
            ".base-search-card__subtitle"
        )

        location_el = card.select_one(
            ".job-search-card__location"
        )

        link_el = card.select_one(
            "a.base-card__full-link"
        )

        time_el = card.select_one(
            "time"
        )


        title = clean(
            title_el.get_text(
                " ",
                strip=True
            )
            if title_el
            else ""
        )


        if not title:

            continue


        company = clean(
            company_el.get_text(
                " ",
                strip=True
            )
            if company_el
            else ""
        )


        location = clean(
            location_el.get_text(
                " ",
                strip=True
            )
            if location_el
            else ""
        )


        job_url = clean_url(
            link_el.get(
                "href",
                ""
            )
            if link_el
            else ""
        )


        posted = ""


        if time_el:

            posted = (
                time_el.get(
                    "datetime",
                    ""
                )
                or
                clean(
                    time_el.get_text(
                        " ",
                        strip=True
                    )
                )
            )


        jobs.append({

            "job_id":
                str(job_id),

            "title":
                title,

            "company":
                company,

            "location":
                location,

            "url":
                job_url,

            "posted":
                posted,

            "query":
                keyword,
        })


    return jobs


# ============================================================
# DESCRIPTION SECTIONS
# ============================================================

TASK_HEADINGS = [

    "responsibilities",

    "your responsibilities",

    "what you will do",

    "what you'll do",

    "your role",

    "your tasks",

    "aufgaben",

    "deine aufgaben",

    "ihre aufgaben",

    "was dich erwartet",

    "tätigkeiten",
]


REQUIREMENT_HEADINGS = [

    "requirements",

    "qualifications",

    "your qualifications",

    "your profile",

    "what you bring",

    "what we are looking for",

    "anforderungen",

    "qualifikationen",

    "dein profil",

    "ihr profil",

    "was du mitbringst",

    "voraussetzungen",
]


def heading_type(text):

    low = clean(
        text
    ).lower()


    for heading in TASK_HEADINGS:

        if heading in low:

            return "tasks"


    for heading in REQUIREMENT_HEADINGS:

        if heading in low:

            return "requirements"


    return "other"


def extract_sections(
    description_el
):

    result = {
        "tasks": [],
        "requirements": [],
        "other": [],
    }


    if not description_el:

        return result


    current = "other"


    for element in (
        description_el.find_all(
            [
                "h2",
                "h3",
                "h4",
                "h5",
                "strong",
                "b",
                "li",
            ]
        )
    ):

        text = clean(
            element.get_text(
                " ",
                strip=True
            )
        )


        if not text:

            continue


        if element.name in [
            "h2",
            "h3",
            "h4",
            "h5",
        ]:

            section = heading_type(
                text
            )


            if section != "other":

                current = section


            continue


        if (
            element.name in [
                "strong",
                "b",
            ]
            and len(text) <= 120
        ):

            section = heading_type(
                text
            )


            if section != "other":

                current = section

                continue


        if element.name == "li":

            if text not in result[
                current
            ]:

                result[
                    current
                ].append(
                    text
                )


    return result


# ============================================================
# JOB DETAILS
# ============================================================

def get_job_details(
    job_id
):

    url = DETAIL_URL.format(
        job_id
    )


    for attempt in range(2):

        try:

            response = SESSION.get(
                url,
                timeout=12
            )

        except Exception as exc:

            print(
                "  Detail error:",
                exc
            )

            return None


        if response.status_code == 200:

            break


        print(
            "  Detail HTTP:",
            response.status_code
        )


        if (
            response.status_code == 429
            and attempt == 0
        ):

            print(
                "  Waiting 8 seconds..."
            )

            time.sleep(8)

            continue


        return None


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    description_el = soup.select_one(
        ".show-more-less-html__markup"
    )


    if not description_el:

        description_el = soup.select_one(
            ".description__text"
        )


    description = clean(
        description_el.get_text(
            " ",
            strip=True
        )
        if description_el
        else ""
    )


    sections = extract_sections(
        description_el
    )


    criteria = {}


    for item in soup.select(
        ".description__job-criteria-item"
    ):

        label_el = item.select_one(
            ".description__job-criteria-subheader"
        )

        value_el = item.select_one(
            ".description__job-criteria-text"
        )


        if (
            not label_el
            or not value_el
        ):

            continue


        label = clean(
            label_el.get_text(
                " ",
                strip=True
            )
        )

        value = clean(
            value_el.get_text(
                " ",
                strip=True
            )
        )


        criteria[
            label
        ] = value


    return {

        "description":
            description,

        "criteria":
            criteria,

        "tasks":
            sections["tasks"],

        "requirements":
            sections["requirements"],

        "other":
            sections["other"],
    }


# ============================================================
# MESSAGE HELPERS
# ============================================================

def add_bullets(
    text,
    heading,
    items,
    limit=15,
):

    if not items:

        return text


    text += (
        f"\n{heading}\n"
    )


    for item in items[:limit]:

        text += (
            f"• {item}\n"
        )


    return text


def build_message(
    job,
    details,
    score,
    matched,
    core_matches,
    required_years,
    experience_status,
    location_status,
    german_status,
    cpp_status,
    employment_status,
):

    if required_years is None:

        years_text = (
            "Not explicitly stated"
        )

    else:

        years_text = (
            f"{required_years}+ years"
        )


    text = (
        "🚨 NEW LINKEDIN JOB\n\n"

        f"💼 {job['title']}\n"

        f"🏢 {job['company']}\n"

        f"📍 {job['location']}\n"

        f"🏠 {location_status}\n"

        f"📅 Posted: "
        f"{job['posted'] or 'Not stated'}\n"

        f"💼 Employment: "
        f"{employment_status}\n\n"

        f"🎯 MATCH SCORE: {score}\n\n"

        "🔥 CORE MATCHES\n"
    )


    for item in core_matches:

        text += (
            f"• {item}\n"
        )


    other_matches = [

        item

        for item in matched

        if item not in core_matches
    ]


    if other_matches:

        text += (
            "\n✅ OTHER MATCHES\n"
        )


        for item in other_matches[:15]:

            text += (
                f"• {item}\n"
            )


    text += (
        "\n⏳ EXPERIENCE\n"

        f"• Arash: ~"
        f"{ARASH_EXPERIENCE_YEARS:g} years\n"

        f"• Job asks: "
        f"{years_text}\n"

        f"• Assessment: "
        f"{experience_status}\n\n"

        "🌐 LANGUAGE / PROGRAMMING\n"

        f"• German: "
        f"{german_status}\n"

        f"• C++: "
        f"{cpp_status}\n"
    )


    criteria = details.get(
        "criteria",
        {}
    )


    if criteria:

        text += (
            "\n📌 JOB CRITERIA\n"
        )


        for key, value in criteria.items():

            text += (
                f"• {key}: {value}\n"
            )


    text = add_bullets(
        text,
        "📋 RESPONSIBILITIES",
        details.get(
            "tasks",
            []
        ),
    )


    text = add_bullets(
        text,
        "🎓 REQUIREMENTS",
        details.get(
            "requirements",
            []
        ),
    )


    if (
        not details.get(
            "tasks"
        )
        and
        not details.get(
            "requirements"
        )
    ):

        text = add_bullets(
            text,
            "📄 JOB DETAILS",
            details.get(
                "other",
                []
            ),
            limit=12,
        )


    text += (
        "\n🔗 OPEN / APPLY\n"
        f"{job['url']}"
    )


    return text


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "=" * 70
    )

    print(
        f"ARASH JOB RADAR - LINKEDIN {VERSION}"
    )

    print(
        "=" * 70
    )


    if TEST_MODE:

        print(
            "TEST MODE ACTIVE"
        )

        print(
            "Telegram: OFF"
        )

        print(
            "Supabase writes: OFF"
        )


    # ========================================================
    # SEARCH
    # ========================================================

    all_jobs = {}


    for number, query in enumerate(
        SEARCH_QUERIES,
        start=1
    ):

        print()

        print(
            f"Searching "
            f"[{number}/{len(SEARCH_QUERIES)}]: "
            f"{query}"
        )


        jobs = search_linkedin_jobs(
            query
        )


        print(
            "Found:",
            len(jobs)
        )


        for job in jobs:

            all_jobs[
                job["job_id"]
            ] = job


        if number < len(
            SEARCH_QUERIES
        ):

            time.sleep(
                SEARCH_DELAY_SECONDS
            )


    print()

    print(
        "=" * 70
    )

    print(
        "TOTAL UNIQUE LINKEDIN JOBS:",
        len(all_jobs)
    )

    print(
        "=" * 70
    )


    # ========================================================
    # SUPABASE DEDUP
    # ========================================================

    jobs_to_check = []


    for job in all_jobs.values():

        if TEST_MODE:

            jobs_to_check.append(
                job
            )

            continue


        if already_seen(
            job["job_id"]
        ):

            print(
                "Already in Supabase:",
                job["job_id"],
                "|",
                job["title"]
            )

            continue


        jobs_to_check.append(
            job
        )


    print(
        "NEW JOBS TO CHECK:",
        len(jobs_to_check)
    )


    sent = 0
    matches = 0
    stored = 0
    detail_requests = 0
    detail_failures = 0


    # ========================================================
    # ANALYSE
    # ========================================================

    for job in jobs_to_check:

        print()

        print(
            "-" * 70
        )

        print(
            job["title"],
            "|",
            job["company"],
            "|",
            job["location"]
        )


        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        if title_is_excluded(
            job["title"]
        ):

            print(
                "Rejected: excluded title."
            )


            if remember_job(
                job,
                "rejected_title"
            ):

                stored += 1


            continue


        # ----------------------------------------------------
        # LOCATION PRECHECK
        # ----------------------------------------------------

        (
            location_candidate,
            pre_location_status,
        ) = location_precheck(
            job["location"]
        )


        if not location_candidate:

            print(
                "Rejected before detail:",
                pre_location_status
            )


            if remember_job(
                job,
                "rejected_location"
            ):

                stored += 1


            continue


        print(
            "Location pre-check:",
            pre_location_status
        )


        # ----------------------------------------------------
        # DETAIL
        # ----------------------------------------------------

        time.sleep(
            DETAIL_DELAY_SECONDS
        )


        detail_requests += 1


        details = get_job_details(
            job["job_id"]
        )


        # IMPORTANT:
        # Do NOT store if LinkedIn detail failed.
        # It will be retried next run.
        if details is None:

            print(
                "Detail unavailable."
            )

            print(
                "NOT saved - will retry later."
            )

            detail_failures += 1

            continue


        description = details.get(
            "description",
            ""
        )


        # ----------------------------------------------------
        # EMPLOYMENT TYPE
        # ----------------------------------------------------

        (
            reject_employment,
            employment_status,
        ) = employment_type_status(
            details.get(
                "criteria",
                {}
            )
        )


        if reject_employment:

            print(
                "Rejected employment:",
                employment_status
            )


            if remember_job(
                job,
                "rejected_employment"
            ):

                stored += 1


            continue


        # ----------------------------------------------------
        # FINAL LOCATION
        # ----------------------------------------------------

        (
            location_ok,
            location_status,
        ) = final_location_check(
            job["location"],
            description
        )


        if not location_ok:

            print(
                "Rejected final location:",
                location_status
            )


            if remember_job(
                job,
                "rejected_location"
            ):

                stored += 1


            continue


        full_text = (
            job["title"]
            + " "
            + description
        )


        # ----------------------------------------------------
        # AUTOMOTIVE DOMAIN
        # ----------------------------------------------------

        if not has_automotive_context(
            full_text
        ):

            print(
                "Rejected: no real automotive context."
            )


            if remember_job(
                job,
                "rejected_domain"
            ):

                stored += 1


            continue


        # ----------------------------------------------------
        # EXPERIENCE
        # ----------------------------------------------------

        required_years = (
            extract_experience_years(
                full_text
            )
        )


        (
            experience_status,
            experience_adjustment,
        ) = experience_fit(
            required_years
        )


        # ----------------------------------------------------
        # LANGUAGE
        # ----------------------------------------------------

        (
            german_status,
            german_adjustment,
            german_hard_reject,
        ) = german_requirement(
            full_text
        )


        if german_hard_reject:

            print(
                "Rejected:",
                german_status
            )


            if remember_job(
                job,
                "rejected_language"
            ):

                stored += 1


            continue


        # ----------------------------------------------------
        # C++
        # ----------------------------------------------------

        (
            cpp_status,
            cpp_adjustment,
        ) = cpp_requirement(
            full_text
        )


        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        (
            score,
            matched,
            core_matches,
        ) = calculate_score(

            job["title"],

            description,

            experience_adjustment,

            german_adjustment,

            cpp_adjustment,
        )


        print(
            "Score:",
            score
        )


        print(
            "Core:",
            (
                ", ".join(
                    core_matches
                )
                if core_matches
                else "NONE"
            )
        )


        print(
            "Experience:",
            experience_status
        )


        # ----------------------------------------------------
        # CORE MATCH
        # ----------------------------------------------------

        if not core_matches:

            print(
                "Rejected: no core match."
            )


            if remember_job(
                job,
                "rejected_no_core",
                score
            ):

                stored += 1


            continue


        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        if score < MIN_MATCH_SCORE:

            print(
                "Rejected: low score."
            )


            if remember_job(
                job,
                "rejected_score",
                score
            ):

                stored += 1


            continue


        # ----------------------------------------------------
        # TOO SENIOR
        # ----------------------------------------------------

        if (
            experience_status
            == "Too senior"
            and score < 90
        ):

            print(
                "Rejected: too senior."
            )


            if remember_job(
                job,
                "rejected_senior",
                score
            ):

                stored += 1


            continue


        # ----------------------------------------------------
        # REAL MATCH
        # ----------------------------------------------------

        matches += 1


        print(
            "MATCH"
        )


        message = build_message(

            job,

            details,

            score,

            matched,

            core_matches,

            required_years,

            experience_status,

            location_status,

            german_status,

            cpp_status,

            employment_status,
        )


        # Test mode never sends/stores.
        if TEST_MODE:

            print(
                "TEST MATCH - Telegram suppressed."
            )

            continue


        # ----------------------------------------------------
        # TELEGRAM
        # ----------------------------------------------------

        telegram_ok = (
            send_long_message(
                message
            )
        )


        # Only remember a successful Telegram match
        # after Telegram delivery succeeds.
        if telegram_ok:

            sent += 1


            if remember_job(
                job,
                "sent",
                score,
                True
            ):

                stored += 1


        else:

            print(
                "Telegram failed."
            )

            print(
                "NOT stored - will retry later."
            )


    # ========================================================
    # SUMMARY
    # ========================================================

    print()

    print(
        "=" * 70
    )

    print(
        "LINKEDIN + SUPABASE SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        "Unique jobs found:",
        len(all_jobs)
    )

    print(
        "New jobs checked:",
        len(jobs_to_check)
    )

    print(
        "Detail requests:",
        detail_requests
    )

    print(
        "Detail failures:",
        detail_failures
    )

    print(
        "Matching jobs:",
        matches
    )

    print(
        "Telegram jobs sent:",
        sent
    )

    print(
        "Jobs stored in Supabase:",
        stored
    )

    print(
        "=" * 70
    )

    print(
        "LinkedIn scan finished."
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":

    main()