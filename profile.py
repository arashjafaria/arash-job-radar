# ============================================================
# ARASH PROFESSIONAL PROFILE
# Temporary profile until the updated CV is available
# ============================================================

ARASH_EXPERIENCE_YEARS = 2.0

CURRENT_LOCATION = "Munich, Germany"

CURRENT_COMPANY = "ARRK Engineering GmbH"

EDUCATION = [
    "Deggendorf Institute of Technology"
]

LANGUAGES = {
    "english": "fluent",
    "german": "good working knowledge",
}

LINKEDIN_CERTIFICATIONS = [
    "Advanced Python",
    "Python Data Analysis",
    "Advanced Python: Working with Databases",
    "Using Python with Excel",
    "Programming Foundations: Object-Oriented Design",
]


# ------------------------------------------------------------
# ACCEPTED LOCATIONS
# Munich + surrounding area
# ------------------------------------------------------------
MUNICH_AREA = [
    # Munich
    "münchen",
    "munich",

    # North / North-East
    "garching",
    "eching",
    "unterschleißheim",
    "oberschleißheim",
    "ismaning",
    "hallbergmoos",
    "neufahrn",
    "freising",
    "erding",

    # East
    "asheim",
    "aschheim",
    "feldkirchen",
    "kirchheim",
    "poing",
    "haar",
    "vaterstetten",
    "markt schwaben",

    # South / South-East
    "ottobrunn",
    "unterhaching",
    "taufkirchen",
    "neubiberg",
    "hohenbrunn",
    "brunnthal",
    "pullach",
    "grünwald",

    # West / North-West
    "dachau",
    "karlsfeld",
    "fürstenfeldbruck",
    "germering",
    "puchheim",
    "olching",
    "gröbenzell",
    "maisach",

    # South-West
    "gräfelfing",
    "planegg",
    "krailling",
    "gauting",
    "starnberg",
]


# ------------------------------------------------------------
# REMOTE JOBS
# ------------------------------------------------------------
REMOTE_WORDS = [
    "remote",
    "fully remote",
    "100% remote",
    "home office",
    "homeoffice",
    "work from home",
    "remote germany",
    "remote within germany",
]

# ------------------------------------------------------------
# HARD EXCLUSIONS
# ------------------------------------------------------------

EXCLUDE_WORDS = [
    "praktikant",
    "praktikum",
    "werkstudent",
    "werkstudentin",
    "azubi",
    "auszubild",
    "ausbildung",
    "duales studium",
    "dualer student",
    "studienabschlussarbeit",
    "abschlussarbeit",
    "masterarbeit",
    "bachelorarbeit",
    "thesis",
    "doktorand",
    "promotion",
    "trainee",
    "schülerpraktik",
]


# ------------------------------------------------------------
# SKILL WEIGHTS
# Higher score = more relevant for Arash
# ------------------------------------------------------------

SKILLS = {

    # Very strong automotive/testing skills
    "canoe": 20,
    "capl": 20,
    "uds": 20,

    "diagnostic": 18,
    "diagnostics": 18,
    "diagnose": 18,

    "integration": 18,
    "testing": 18,
    "test engineer": 18,
    "testingenieur": 18,

    "ecu": 16,
    "steuergerät": 16,

    "can fd": 16,
    "can-fd": 16,
    "can bus": 14,

    "hil": 16,
    "sil": 16,

    # Python is now weighted higher
    "python": 18,
    "python automation": 18,
    "scripting": 10,

    "validation": 14,
    "verification": 14,

    "automotive ethernet": 14,
    "ethernet": 10,

    "radar": 14,
    "adas": 14,

    "embedded": 12,

    "test automation": 18,
    "testautomatisierung": 18,
    "automatisierung": 10,

    "software testing": 14,

    "fahrzeugintegration": 14,
    "vehicle integration": 14,

    "e/e": 10,

    # Supporting Python/Data skills from LinkedIn
    "object oriented": 8,
    "object-oriented": 8,
    "oop": 8,
    "database": 7,
    "databases": 7,
    "sql": 7,
    "data analysis": 6,
    "excel": 3,

    # General words have low weight
    "software": 6,
    "fahrzeug": 4,
    "vehicle": 4,
}


# ------------------------------------------------------------
# ROLE WORDS
# ------------------------------------------------------------

GOOD_ROLE_WORDS = [
    "entwicklungsingenieur",
    "development engineer",
    "test engineer",
    "testingenieur",
    "integration engineer",
    "integrationsingenieur",
    "validation engineer",
    "system engineer",
    "systemingenieur",
    "diagnostic",
    "diagnose",
    "software test",
    "test automation",
    "verification",
]