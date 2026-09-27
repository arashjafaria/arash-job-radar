import re

from profile import (
    ARASH_EXPERIENCE_YEARS,
    MAX_REQUIRED_EXPERIENCE_YEARS,
    MIN_MATCH_PERCENT,
    SENIOR_MIN_MATCH_PERCENT,
    MUNICH_AREA,
    SPECIAL_ONSITE_EXCEPTIONS,
    REMOTE_WORDS,
    SKILL_LEVELS,
    SKILL_ALIASES,
    GOOD_ROLE_WORDS,
    DRIVING_LICENSE_B,
)

LEVEL_NAMES = {1: "Basic", 2: "Intermediate", 3: "Professional"}

ACTIVITY_TERMS = [
    "requirements", "requirement", "anforderung",
    "system testing", "system test", "systemtest",
    "integration testing", "integration test", "integration",
    "validation", "validierung",
    "verification", "verifikation",
    "regression", "regressionstest",
    "diagnostic", "diagnostics", "diagnose",
    "defect", "fehleranalyse", "issue analysis",
    "root cause", "ursachenanalyse",
    "software release", "release",
    "flashing", "flashen",
    "log analysis", "logging", "log-analyse",
    "test automation", "testautomatisierung",
    "scripting", "script",
    "supplier", "lieferant", "oem",
    "coordination", "koordination",
    "test case", "testfall",
    "test execution", "testdurchführung",
    "reporting", "technical findings",
]

ADVANCED_WORDS = [
    "advanced", "expert", "professional", "proficient",
    "strong", "excellent", "extensive", "deep knowledge",
    "very good", "sehr gute", "fundierte",
    "umfangreiche", "expertenkenntnisse", "tiefgreifende",
]

INTERMEDIATE_WORDS = [
    "intermediate", "good knowledge", "good experience",
    "gute kenntnisse", "gute erfahrung",
]

SENIOR_TITLE_WORDS = [
    "senior", "lead engineer", "principal",
    "technical lead", "team lead", "head of", "senior expert",
]


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _term_present(term, text):
    if not term or not text:
        return False
    term = term.strip().lower()
    if not term:
        return False
    pattern = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
    return bool(re.search(pattern, text.lower(), flags=re.IGNORECASE))


def _skill_present(skill, text):
    return any(
        _term_present(alias, text)
        for alias in SKILL_ALIASES.get(skill, [skill])
    )


def required_skill_level(text):
    low = (text or "").lower()
    if any(word in low for word in ADVANCED_WORDS):
        return 3
    if any(word in low for word in INTERMEDIATE_WORDS):
        return 2
    return 1


def skill_fit_percent(candidate_level, required_level):
    if candidate_level >= required_level:
        return 100
    gap = required_level - candidate_level
    if gap == 1:
        return 75
    return 45


def detected_skill_scores(text):
    result = {}
    for skill, candidate_level in SKILL_LEVELS.items():
        if not _skill_present(skill, text):
            continue
        req_level = required_skill_level(text)
        result[skill] = {
            "candidate_level": candidate_level,
            "required_level": req_level,
            "fit": skill_fit_percent(candidate_level, req_level),
        }
    return result


def _qualification_score(text, default_unknown):
    low = (text or "").lower()
    skills = detected_skill_scores(text)
    if skills:
        return round(sum(v["fit"] for v in skills.values()) / len(skills))

    if any(term in low for term in ACTIVITY_TERMS):
        return 100

    degree_terms = [
        "bachelor", "master", "engineering degree", "degree in engineering",
        "studium", "hochschulabschluss", "ingenieurstudium",
        "electrical engineering", "elektrotechnik",
        "mechatronics", "mechatronik",
    ]
    if any(term in low for term in degree_terms):
        return 100

    licence_terms = [
        "driving licence", "driving license", "führerschein",
        "fuehrerschein", "klasse b", "class b",
    ]
    if any(term in low for term in licence_terms):
        return 100 if DRIVING_LICENSE_B else 0

    coordination_terms = [
        "communication", "teamwork", "team player", "coordination",
        "stakeholder", "kommunikation", "teamfähigkeit",
        "teamfaehigkeit", "abstimmung",
    ]
    if any(term in low for term in coordination_terms):
        return 90

    return default_unknown


def _section_fit(items, default_unknown):
    items = [clean(item) for item in (items or []) if clean(item)]
    if not items:
        return 60
    scores = [_qualification_score(item, default_unknown) for item in items]
    return round(sum(scores) / len(scores))


def _technology_fit(description, requirements, tasks):
    weighted = []

    for item in requirements or []:
        for value in detected_skill_scores(item).values():
            weighted.extend([value["fit"], value["fit"]])

    for item in tasks or []:
        for value in detected_skill_scores(item).values():
            weighted.append(value["fit"])

    if not weighted:
        for value in detected_skill_scores(description).values():
            weighted.append(value["fit"])

    if not weighted:
        return 60

    return round(sum(weighted) / len(weighted))


def _role_fit(title):
    low = (title or "").lower()
    for role in GOOD_ROLE_WORDS:
        if role in low:
            return 100

    generic = [
        "engineer", "ingenieur", "tester", "testing",
        "validation", "verification", "requirements",
        "system", "entwicklung",
    ]
    if any(term in low for term in generic):
        return 80
    return 50


def evaluate_fit(title, description, requirements=None, tasks=None):
    requirements = requirements or []
    tasks = tasks or []

    req_fit = _section_fit(requirements, 55)
    tech_fit = _technology_fit(description, requirements, tasks)
    task_fit = _section_fit(tasks, 65)
    role_fit = _role_fit(title)

    fit = round(
        req_fit * 0.45
        + tech_fit * 0.25
        + task_fit * 0.20
        + role_fit * 0.10
    )
    fit = max(0, min(100, fit))

    all_text = " ".join([
        title or "",
        description or "",
        " ".join(requirements),
        " ".join(tasks),
    ])
    detected = detected_skill_scores(all_text)
    matched = sorted(detected.keys())

    warnings = []
    for skill, value in detected.items():
        if value["required_level"] > value["candidate_level"]:
            warnings.append(
                "⚠️ "
                + skill
                + ": job appears to request "
                + LEVEL_NAMES[value["required_level"]]
                + "; Arash profile: "
                + LEVEL_NAMES[value["candidate_level"]]
            )

    breakdown = {
        "requirements": req_fit,
        "technology": tech_fit,
        "responsibilities": task_fit,
        "role": role_fit,
    }

    return fit, matched, warnings, breakdown


def extract_experience_years(text):
    low = (text or "").lower()
    values = []

    range_patterns = [
        r"(\d+)\s*(?:-|–|—|to|bis)\s*(\d+)\s*years?",
        r"(\d+)\s*(?:-|–|—|bis)\s*(\d+)\s*jahre",
    ]
    for pattern in range_patterns:
        for first, second in re.findall(pattern, low):
            values.extend([int(first), int(second)])

    patterns = [
        r"(\d+)\s*\+\s*years?",
        r"(\d+)\s*\+\s*jahre",
        r"(\d+)\s*years?\s+(?:of\s+)?experience",
        r"at least\s+(\d+)\s+years?",
        r"minimum(?: of)?\s+(\d+)\s+years?",
        r"mindestens\s+(\d+)\s+jahre",
        r"min\.\s*(\d+)\s+jahre",
        r"(\d+)\s+jahre\s+berufserfahrung",
        r"(\d+)\s+jährige\s+berufserfahrung",
    ]
    for pattern in patterns:
        for value in re.findall(pattern, low):
            try:
                values.append(int(value))
            except Exception:
                pass

    more_than = [
        r"more than\s+(\d+)\s+years?",
        r"over\s+(\d+)\s+years?",
        r"mehr als\s+(\d+)\s+jahre",
    ]
    for pattern in more_than:
        for value in re.findall(pattern, low):
            try:
                values.append(int(value) + 1)
            except Exception:
                pass

    if not values:
        return None
    return max(values)


def experience_status(required_years):
    if required_years is None:
        return False, "Not explicitly stated"

    if required_years > MAX_REQUIRED_EXPERIENCE_YEARS:
        return (
            True,
            f"Requires {required_years}+ years; maximum accepted is "
            f"{MAX_REQUIRED_EXPERIENCE_YEARS}",
        )

    return False, "Within accepted experience range"


def german_requirement(text):
    low = (text or "").lower()

    native_patterns = [
        r"native german",
        r"german native",
        r"deutsch.{0,40}muttersprache",
        r"muttersprache.{0,40}deutsch",
        r"deutsch.{0,40}muttersprach",
    ]
    for pattern in native_patterns:
        if re.search(pattern, low):
            return True, "German native / Muttersprache explicitly required", -100

    c_patterns = [
        r"german.{0,40}\bc1\b",
        r"deutsch.{0,40}\bc1\b",
        r"\bc1\b.{0,40}german",
        r"\bc1\b.{0,40}deutsch",
        r"german.{0,40}\bc2\b",
        r"deutsch.{0,40}\bc2\b",
        r"verhandlungssicher.{0,40}deutsch",
        r"deutsch.{0,40}verhandlungssicher",
        r"fluent.{0,30}german",
        r"german.{0,30}fluent",
        r"fließend.{0,30}deutsch",
        r"fliessend.{0,30}deutsch",
        r"sehr gute deutschkenntnisse",
    ]
    for pattern in c_patterns:
        if re.search(pattern, low):
            return False, "⚠️ German C1/C2/fluent requested; current level B1", -10

    b2_patterns = [
        r"german.{0,40}\bb2\b",
        r"deutsch.{0,40}\bb2\b",
        r"\bb2\b.{0,40}german",
        r"\bb2\b.{0,40}deutsch",
    ]
    for pattern in b2_patterns:
        if re.search(pattern, low):
            return False, "⚠️ German B2 requested; current level B1", -5

    b1_patterns = [
        r"german.{0,40}\bb1\b",
        r"deutsch.{0,40}\bb1\b",
        r"\bb1\b.{0,40}german",
        r"\bb1\b.{0,40}deutsch",
    ]
    for pattern in b1_patterns:
        if re.search(pattern, low):
            return False, "German B1 requested; matches current level", 0

    return False, "No explicit German level detected", 0


def contract_status(criteria, description):
    values = []
    for key, value in (criteria or {}).items():
        key_low = str(key).lower()
        if any(
            term in key_low
            for term in [
                "employment", "beschäftigungsart", "beschaeftigungsart",
                "anstellungsart", "contract", "vertrag",
            ]
        ):
            values.append(str(value))

    full = (" ".join(values) + " " + (description or "")).lower()

    reject_patterns = [
        r"\bpart[- ]time\b",
        r"\bteilzeit\b",
        r"\bfixed[- ]term\b",
        r"\bbefristet\b",
        r"\btemporary contract\b",
        r"\bfreelance\b",
        r"\bfreelancer\b",
        r"\bself[- ]employed\b",
        r"\barbeitnehmerüberlassung\b",
        r"\barbeitnehmerueberlassung\b",
    ]
    for pattern in reject_patterns:
        if re.search(pattern, full):
            return True, "Non-permanent or non-full-time contract detected"

    positive_patterns = [
        r"\bfull[- ]time\b",
        r"\bvollzeit\b",
        r"\bpermanent\b",
        r"\bunbefristet\b",
    ]
    if any(re.search(pattern, full) for pattern in positive_patterns):
        return False, "Permanent/full-time compatible"

    return False, "Contract type not stated"


def location_status(location, description):
    location_low = (location or "").lower()
    full = ((location or "") + " " + (description or "")).lower()

    for city in MUNICH_AREA:
        if city in location_low:
            return True, "Onsite/hybrid within accepted Munich ~150 km area"

    for city in SPECIAL_ONSITE_EXCEPTIONS:
        if city in location_low:
            return True, "Accepted onsite exception: Nuremberg"

    negative_remote = [
        "no remote", "not remote", "kein remote",
        "nicht remote", "kein homeoffice", "keine homeoffice",
    ]
    remote_found = any(word.lower() in full for word in REMOTE_WORDS)
    germany_context = any(
        term in full
        for term in ["germany", "deutschland", "bundesweit"]
    )

    if (
        remote_found
        and germany_context
        and not any(phrase in full for phrase in negative_remote)
    ):
        return True, "Remote Germany"

    return False, "Onsite/hybrid location outside accepted ~150 km Munich area"


def is_senior_title(title):
    low = (title or "").lower()
    return any(word in low for word in SENIOR_TITLE_WORDS)


def security_warnings(text):
    low = (text or "").lower()
    terms = [
        "german citizenship",
        "deutsche staatsangehörigkeit",
        "deutsche staatsangehoerigkeit",
        "eu citizenship",
        "eu-bürgerschaft",
        "eu-buergerschaft",
        "nato citizenship",
        "security clearance",
        "sicherheitsüberprüfung",
        "sicherheitsueberpruefung",
        "ü2", "ue2", "ü3", "ue3",
    ]

    if any(term in low for term in terms):
        return ["⚠️ Citizenship/security-clearance requirement detected"]
    return []
