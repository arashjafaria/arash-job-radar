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

LEVEL_NAMES = {
    1: "Basic",
    2: "Intermediate",
    3: "Professional",
}

# ------------------------------------------------------------------
# Matching philosophy
# ------------------------------------------------------------------
# Requirements drive the decision.
#   Requirements / qualifications: 80%
#   Responsibilities:              15%
#   Role/title similarity:          5%
#
# A job is allowed only when:
#   requirement fit >= 60%
#   core technical/domain fit >= 50%
#   overall fit >= 60%
#
# Unknown technical requirements receive 0, not a neutral default.
# Generic soft requirements carry only a very small weight.

DIRECT_ACTIVITY_TERMS = [
    "requirements-based testing",
    "requirement based testing",
    "requirements engineering",
    "requirement engineering",
    "anforderungsmanagement",
    "anforderungsanalyse",
    "system testing",
    "system test",
    "systemtest",
    "system integration testing",
    "integration testing",
    "validation",
    "validierung",
    "verification",
    "verifikation",
    "regression testing",
    "regression test",
    "regressionstest",
    "diagnostic testing",
    "diagnostics",
    "diagnose",
    "defect analysis",
    "fehleranalyse",
    "root cause",
    "ursachenanalyse",
    "ecu log analysis",
    "log analysis",
    "flashing",
    "test automation",
    "testautomatisierung",
    "test execution",
    "testdurchführung",
    "test case",
    "testfall",
    "software release",
    "release testing",
]

TRANSFERABLE_ACTIVITY_TERMS = [
    "integration",
    "testing",
    "test",
    "qualification",
    "qualifikation",
    "test campaign",
    "testkampagne",
    "laboratory",
    "labor",
    "test infrastructure",
    "testumgebung",
    "prototyping",
    "prototype testing",
    "technical coordination",
    "stakeholder",
    "supplier",
    "lieferant",
    "oem",
    "reporting",
    "technical findings",
    "engineering analysis",
]

BENEFIT_TERMS = [
    "attraktive vergütung",
    "attraktive verguetung",
    "competitive salary",
    "salary",
    "vergütung",
    "verguetung",
    "benefits",
    "weiterentwicklungsmöglichkeiten",
    "weiterentwicklungsmoeglichkeiten",
    "development opportunities",
    "career development",
    "wachstumsorientierten umfeld",
    "flexible arbeitszeiten",
    "flexible working hours",
    "home-office-möglichkeiten",
    "home-office-moeglichkeiten",
    "work-life-balance",
    "work life balance",
    "urlaub",
    "vacation",
    "pension",
    "betriebliche altersvorsorge",
]

INTEREST_TERMS = [
    "interesse an",
    "interest in",
    "begeisterung für",
    "begeisterung fuer",
    "passion for",
]

SOFT_SKILL_TERMS = [
    "problem-solving",
    "problem solving",
    "analytical thinking",
    "communication",
    "teamwork",
    "team player",
    "teamfähigkeit",
    "teamfaehigkeit",
    "communication skills",
    "kommunikationsfähigkeit",
    "kommunikationsfaehigkeit",
    "self-motivated",
    "independent working",
    "selbstständig",
    "selbststaendig",
    "under pressure",
    "fast-paced",
    "pragmatism",
    "ownership",
    "hands-on mentality",
]

# Strong indicators that the requirement belongs to a technical domain
# not supported by the current CV/profile. These are not industry bans:
# only the specific requirement receives 0.
OUT_OF_PROFILE_TECH = [
    "mechanical design",
    "structural analysis",
    "solidworks",
    "cad",
    "catia",
    "creo",
    "finite element",
    "fea",
    "cnc",
    "milling",
    "turning",
    "laser cutting",
    "additive manufacturing",
    "manufacturing of metal",
    "manufacturing of plastic",
    "fabrication",
    "space hardware development",
    "satellite hardware",
    "payload hardware",
    "solar array",
    "thermal analysis",
    "thermal design",
    "composite design",
    "mechanical systems",
    "mechanical engineering design",
    "pcb layout",
    "rf design",
    "analog circuit design",

    # AI / ML / robotics software not supported by Arash's current CV/profile
    "machine learning",
    "deep learning",
    "ai engineering",
    "artificial intelligence",
    "künstliche intelligenz",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "sklearn",
    "opencv",
    "computer vision",
    "mlops",
    "docker",
    "edge deployment",
    "model training",
    "modelltraining",
    "model deployment",
    "model monitoring",
    "datenaufbereitung",
    "data preparation",
    "data preprocessing",
    "2d data",
    "3d data",
    "2d-daten",
    "3d-daten",
    "sensordatenverarbeitung",
    "sensor data processing",
    "algorithm optimization",
    "algorithmenoptimierung",
    "arm",
    "nvidia gpu",
    "gpu optimization",
    "cuda",
    "ros",
    "ros2",
    "kubernetes",
    "matlab",
    "simulink",
    "labview",
    "fpga",
    "ansys",
]

# Context that indicates a transferable activity is being performed in
# a substantially different hardware/domain environment.
DOMAIN_DISTANCE_TERMS = [
    "satellite",
    "payload",
    "space hardware",
    "solar array",
    "mechanical",
    "structural",
    "manufacturing",
    "fabrication",
    "cnc",
    "milling",
    "turning",
    "vibration",
    "shock",
    "thermal",
    "aerospace",
    "space",
    "breadboard",
    "engineering model",
    "development hardware",

    # Process / medical-product development is not the same validation domain
    # as ECU/system/software V&V.
    "process validation",
    "validierung von prozessen",
    "prozessvalidierung",
    "qualification of processes",
    "qualifizierung von prozessen",
    "production process",
    "produktionsprozess",
    "medical device",
    "medizintechnik",
    "medizinische einwegprodukte",
    "design control",
    "iq/oq/pq",
    "peritonealdialyse",
    "blutreinigung",
]

TECHNICAL_MARKERS = [
    "experience with",
    "experience in",
    "experience developing",
    "knowledge of",
    "knowledge in",
    "expertise",
    "proficiency",
    "proficient",
    "strong",
    "advanced",
    "design",
    "development",
    "developing",
    "hardware",
    "software",
    "system",
    "systems",
    "tool",
    "tools",
    "protocol",
    "programming",
    "testing",
    "test",
    "validation",
    "verification",
    "integration",
    "diagnostic",
    "engineering",
    "erfahrung mit",
    "erfahrung in",
    "praktische erfahrung",
    "kenntnisse",
    "framework",
    "frameworks",
    "modell",
    "model",
    "training",
    "deployment",
    "monitoring",
    "algorithm",
    "algorithmen",
    "optimierung",
    "datenaufbereitung",
    "sensordatenverarbeitung",
    "computer vision",
    "machine learning",
    "deep learning",
    "mlops",
]

ADVANCED_WORDS = [
    "advanced",
    "expert",
    "professional",
    "proficient",
    "strong",
    "excellent",
    "extensive",
    "deep knowledge",
    "very good",
    "sehr gute",
    "fundierte",
    "umfangreiche",
    "expertenkenntnisse",
    "tiefgreifende",
    "sicher in",
    "sicher mit",
    "sicherer umgang",
]

INTERMEDIATE_WORDS = [
    "intermediate",
    "good knowledge",
    "good experience",
    "gute kenntnisse",
    "gute erfahrung",
]

SENIOR_TITLE_WORDS = [
    "senior",
    "lead engineer",
    "principal",
    "technical lead",
    "team lead",
    "head of",
    "senior expert",
]


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _term_present(term, text):
    if not term or not text:
        return False

    term = term.strip().lower()
    if not term:
        return False

    pattern = (
        r"(?<![A-Za-z0-9])"
        + re.escape(term)
        + r"(?![A-Za-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            text.lower(),
            flags=re.IGNORECASE,
        )
    )


def _any_term(terms, text):
    return any(
        _term_present(
            term,
            text,
        )
        for term in terms
    )


def _skill_aliases(skill):
    return SKILL_ALIASES.get(
        skill,
        [skill],
    )


def _skill_present(skill, text):
    return any(
        _term_present(alias, text)
        for alias in _skill_aliases(skill)
    )


def _required_level_for_skill(skill, text):
    low = (text or "").lower()

    windows = []

    for alias in _skill_aliases(skill):
        alias_low = alias.strip().lower()
        if not alias_low:
            continue

        start = 0

        while True:
            pos = low.find(alias_low, start)
            if pos < 0:
                break

            windows.append(
                low[
                    max(0, pos - 55):
                    min(len(low), pos + len(alias_low) + 55)
                ]
            )

            start = pos + len(alias_low)

    if not windows:
        windows = [low]

    local = " ".join(windows)

    if any(
        word in local
        for word in ADVANCED_WORDS
    ):
        return 3

    if any(
        word in local
        for word in INTERMEDIATE_WORDS
    ):
        return 2

    return 1


def skill_fit_percent(
    candidate_level,
    required_level,
):
    if candidate_level >= required_level:
        return 100

    if required_level - candidate_level == 1:
        return 70

    return 40


def detected_skill_scores(text):
    result = {}

    for skill, candidate_level in SKILL_LEVELS.items():
        if not _skill_present(skill, text):
            continue

        req_level = _required_level_for_skill(
            skill,
            text,
        )

        result[skill] = {
            "candidate_level": candidate_level,
            "required_level": req_level,
            "fit": skill_fit_percent(
                candidate_level,
                req_level,
            ),
        }

    return result


def _experience_domain_score(text):
    """
    Duration is checked separately as a hard gate.
    This function checks whether the field attached to an experience
    requirement is supported by Arash's background.
    """
    low = (text or "").lower()

    if not re.search(
        r"\b\d+\s*\+?\s*(?:years?|jahre)\b",
        low,
    ):
        return None

    if _any_term(
        OUT_OF_PROFILE_TECH,
        low,
    ):
        return 0

    skills = detected_skill_scores(
        low
    )

    if skills:
        return round(
            max(
                value["fit"]
                for value in skills.values()
            )
        )

    if _any_term(
        DIRECT_ACTIVITY_TERMS,
        low,
    ):
        return 100

    if _any_term(
        TRANSFERABLE_ACTIVITY_TERMS,
        low,
    ):
        if _any_term(
            DOMAIN_DISTANCE_TERMS,
            low,
        ):
            return 40

        return 70

    # A duration requirement whose domain cannot be tied to
    # the CV is not assumed to match.
    return 0


def _education_result(text):
    low = (text or "").lower()

    if not any(
        term in low
        for term in [
            "bachelor",
            "master",
            "degree",
            "studium",
            "hochschulabschluss",
        ]
    ):
        return None

    direct_fields = [
        "electrical engineering",
        "elektrotechnik",
        "mechatronics",
        "mechatronik",
        "cyber-physical",
        "cyber physical",
        "automation engineering",
        "automatisierungstechnik",
    ]

    if any(
        field in low
        for field in direct_fields
    ):
        return 100

    if any(
        term in low
        for term in [
            "related field",
            "related discipline",
            "vergleichbar",
            "vergleichbare",
            "verwandte fachrichtung",
        ]
    ):
        return 70

    return 30


def _english_result(text):
    low = (text or "").lower()

    if not any(
        term in low
        for term in [
            "english",
            "englisch",
        ]
    ):
        return None

    if any(
        term in low
        for term in [
            "native english",
            "english native",
            "mother tongue english",
            "englisch muttersprache",
        ]
    ):
        return 40

    if any(
        term in low
        for term in [
            "fluent english",
            "fluent in english",
            "excellent english",
            "very good english",
            "verhandlungssicheres englisch",
            "verhandlungssicher englisch",
        ]
    ):
        return 70

    return 100


def _admin_result(text):
    low = (text or "").lower()

    if any(
        term in low
        for term in [
            "eligible to work in germany",
            "work authorization",
            "work authorisation",
            "arbeitserlaubnis",
            "work permit",
        ]
    ):
        return {
            "score": 100,
            "weight": 0.0,
            "category": "administrative",
            "core": False,
            "reason": "Work authorization compatible",
        }

    if any(
        term in low
        for term in [
            "driving licence",
            "driving license",
            "führerschein",
            "fuehrerschein",
            "klasse b",
            "class b",
        ]
    ):
        return {
            "score": 100 if DRIVING_LICENSE_B else 0,
            "weight": 1.0,
            "category": "administrative",
            "core": False,
            "reason": (
                "Driving licence B matches"
                if DRIVING_LICENSE_B
                else "Driving licence requirement not met"
            ),
        }

    return None


def split_requirement_phrase(text):
    """
    Split compound requirement bullets into meaningful atomic clauses.
    AND/UND/SOWIE creates separate mandatory clauses.
    OR/ODER stays inside a clause because one alternative may satisfy it.
    Hyphenated German constructions such as "Deutsch- und Englisch"
    are deliberately not split.
    """
    phrase = clean(text)

    if not phrase:
        return []

    # Benefits are kept as one unit and ignored later.
    if _any_term(
        BENEFIT_TERMS,
        phrase,
    ):
        return [phrase]

    parts = re.split(
        r"\s*;\s*|(?<!-)\s+(?:sowie|und|and)\s+",
        phrase,
        flags=re.IGNORECASE,
    )

    parts = [
        clean(part.strip(" ,"))
        for part in parts
        if clean(part.strip(" ,"))
    ]

    if len(parts) <= 1:
        return [phrase]

    # Avoid producing meaningless fragments from conjunctions.
    useful = []

    for part in parts:
        if len(part) < 3:
            continue

        useful.append(
            part
        )

    return useful or [phrase]


def evaluate_requirement_phrase(text):
    phrase = clean(text)

    if not phrase:
        return None

    low = phrase.lower()

    if _any_term(
        BENEFIT_TERMS,
        low,
    ):
        return {
            "text": phrase,
            "score": 0,
            "weight": 0.0,
            "category": "benefit",
            "core": False,
            "reason": "Benefit/non-requirement; excluded from scoring",
        }

    admin = _admin_result(
        phrase
    )

    if admin:
        return {
            "text": phrase,
            **admin,
        }

    # "Interest in ..." is not evidence of technical competence.
    if _any_term(
        INTEREST_TERMS,
        low,
    ):
        skills = detected_skill_scores(
            phrase
        )

        return {
            "text": phrase,
            "score": 100 if skills else 70,
            "weight": 0.5,
            "category": "interest",
            "core": False,
            "reason": "Interest/familiarity requirement; very low weight",
        }

    exp_domain = _experience_domain_score(
        phrase
    )

    if exp_domain is not None:
        return {
            "text": phrase,
            "score": exp_domain,
            "weight": 5.0,
            "category": "experience-domain",
            "core": True,
            "reason": (
                "Required experience field supported"
                if exp_domain >= 70
                else (
                    "Experience is only partly transferable"
                    if exp_domain > 0
                    else "Required experience field is not supported by CV/profile"
                )
            ),
        }

    unsupported_hits = [
        term
        for term in OUT_OF_PROFILE_TECH
        if _term_present(
            term,
            low,
        )
    ]

    skills = detected_skill_scores(
        phrase
    )

    if (
        unsupported_hits
        and skills
    ):
        fits = [
            value["fit"]
            for value in skills.values()
        ]

        # Mixed clauses with "or/oder" or example wording mean a known
        # technology may satisfy part of the requirement, but not all of it.
        alternative_context = (
            bool(
                re.search(
                    r"\b(?:or|oder)\b",
                    low,
                )
            )
            or "zum beispiel" in low
            or "for example" in low
            or "such as" in low
            or "beispielsweise" in low
        )

        mixed_score = (
            max(fits)
            if alternative_context
            else round(
                (
                    sum(fits)
                    + 0 * len(unsupported_hits)
                )
                / (
                    len(fits)
                    + len(unsupported_hits)
                )
            )
        )

        mixed_score = min(
            mixed_score,
            70,
        )

        return {
            "text": phrase,
            "score": mixed_score,
            "weight": 5.0,
            "category": "mixed-technical",
            "core": True,
            "reason": (
                "Partial technical match; unsupported: "
                + ", ".join(
                    unsupported_hits[:6]
                )
            ),
        }

    if unsupported_hits:
        return {
            "text": phrase,
            "score": 0,
            "weight": 5.0,
            "category": "core-technical",
            "core": True,
            "reason": (
                "Core technical requirement not supported: "
                + ", ".join(
                    unsupported_hits[:6]
                )
            ),
        }

    if skills:
        fits = [
            value["fit"]
            for value in skills.values()
        ]

        # "A or B" means one alternative can satisfy the requirement.
        if re.search(
            r"\b(?:or|oder)\b",
            low,
        ):
            skill_score = max(
                fits
            )
        else:
            skill_score = round(
                sum(fits)
                / len(fits)
            )

        named = ", ".join(
            sorted(
                skills.keys()
            )
        )

        return {
            "text": phrase,
            "score": skill_score,
            "weight": 5.0,
            "category": "core-technical",
            "core": True,
            "reason": "Matched profile skills: " + named,
        }

    education = _education_result(
        phrase
    )

    if education is not None:
        education_weight = (
            4.0
            if education < 70
            else 2.0
        )

        return {
            "text": phrase,
            "score": education,
            "weight": education_weight,
            "category": "education",
            "core": education < 70,
            "reason": (
                "Education directly matches"
                if education == 100
                else (
                    "Education is reasonably related"
                    if education >= 70
                    else "Requested mandatory education field differs from CV"
                )
            ),
        }

    english = _english_result(
        phrase
    )

    if english is not None:
        return {
            "text": phrase,
            "score": english,
            "weight": 1.0,
            "category": "language",
            "core": False,
            "reason": (
                "English requirement compatible"
                if english >= 70
                else "English requirement stronger than CV level"
            ),
        }

    if _any_term(
        DIRECT_ACTIVITY_TERMS,
        low,
    ):
        if _any_term(
            DOMAIN_DISTANCE_TERMS,
            low,
        ):
            direct_score = 70
            direct_reason = (
                "Direct activity match, but in a substantially different domain"
            )
        else:
            direct_score = 100
            direct_reason = "Directly supported by current CV responsibilities"

        return {
            "text": phrase,
            "score": direct_score,
            "weight": 4.0,
            "category": "core-activity",
            "core": True,
            "reason": direct_reason,
        }

    if _any_term(
        TRANSFERABLE_ACTIVITY_TERMS,
        low,
    ):
        if _any_term(
            DOMAIN_DISTANCE_TERMS,
            low,
        ):
            score = 40
            reason = "Activity is transferable but in a substantially different domain"
        else:
            score = 70
            reason = "Strongly transferable engineering activity"

        return {
            "text": phrase,
            "score": score,
            "weight": 3.0,
            "category": "transferable",
            "core": score >= 70,
            "reason": reason,
        }

    if _any_term(
        SOFT_SKILL_TERMS,
        low,
    ):
        return {
            "text": phrase,
            "score": 90,
            "weight": 0.5,
            "category": "soft-skill",
            "core": False,
            "reason": "General professional requirement",
        }

    if _any_term(
        TECHNICAL_MARKERS,
        low,
    ):
        # The text looks technical, but it is not in our known vocabulary.
        # Do not assume it is a mismatch. Keep it visible as uncertain and
        # exclude it from the percentage unless we have explicit evidence.
        return {
            "text": phrase,
            "score": 0,
            "weight": 0.0,
            "category": "uncertain-technical",
            "core": False,
            "reason": (
                "Technical-looking requirement not confidently classified; "
                "excluded from scoring and not used alone to reject"
            ),
        }

    # Generic/unclassified wording is visible for audit, but does not
    # improve or reduce the requirement percentage.
    return {
        "text": phrase,
        "score": 0,
        "weight": 0.0,
        "category": "unclassified",
        "core": False,
        "reason": "Unclassified/non-technical wording; excluded from scoring",
    }


def _weighted_score(details):
    scored = [
        item
        for item in details
        if item
        and item["weight"] > 0
    ]

    if not scored:
        return 0

    numerator = sum(
        item["score"]
        * item["weight"]
        for item in scored
    )

    denominator = sum(
        item["weight"]
        for item in scored
    )

    return round(
        numerator
        / denominator
    )


def evaluate_requirements(
    requirements,
    description,
):
    source_phrases = [
        clean(item)
        for item in (requirements or [])
        if clean(item)
    ]

    phrases = []

    for source_phrase in source_phrases:
        phrases.extend(
            split_requirement_phrase(
                source_phrase
            )
        )

    # If structured requirement bullets could not be parsed, do not invent
    # a positive score from the title. We only inspect sentences that clearly
    # look like qualification/requirement statements.
    if not phrases:
        sentences = re.split(
            r"(?<=[.!?])\s+",
            description or "",
        )

        requirement_cues = [
            "required",
            "requirements",
            "you bring",
            "what you bring",
            "must have",
            "experience",
            "knowledge",
            "degree",
            "qualifications",
            "anforderung",
            "profil",
            "kenntnisse",
            "erfahrung",
            "studium",
        ]

        fallback_phrases = [
            clean(sentence)
            for sentence in sentences
            if clean(sentence)
            and any(
                cue in sentence.lower()
                for cue in requirement_cues
            )
        ][:15]

        phrases = []

        for fallback_phrase in fallback_phrases:
            phrases.extend(
                split_requirement_phrase(
                    fallback_phrase
                )
            )

    details = [
        evaluate_requirement_phrase(
            phrase
        )
        for phrase in phrases
    ]

    details = [
        item
        for item in details
        if item
    ]

    scored_details = [
        item
        for item in details
        if item.get("weight", 0) > 0
    ]

    requirement_fit = _weighted_score(
        details
    )

    # Fail-open rule: if the parser cannot confidently classify any real
    # requirement, do not reject the job just because our vocabulary is
    # incomplete. Give the requirement section a neutral pass threshold and
    # let hard filters / known mismatches decide.
    if not scored_details:
        requirement_fit = MIN_MATCH_PERCENT

    core_details = [
        item
        for item in details
        if item["core"]
        and item["weight"] > 0
    ]

    if core_details:
        core_fit = _weighted_score(
            core_details
        )
    else:
        # No explicit core requirement means the core gate does not
        # independently reject the job.
        core_fit = 100

    return (
        requirement_fit,
        core_fit,
        details,
    )


def evaluate_responsibilities(tasks):
    details = []

    for task in tasks or []:
        phrase = clean(task)

        if not phrase:
            continue

        low = phrase.lower()

        if _any_term(
            OUT_OF_PROFILE_TECH,
            low,
        ):
            score = 20
            reason = "Responsibility is mostly outside current technical background"

        elif detected_skill_scores(
            phrase
        ):
            score = 100
            reason = "Direct tool/technology overlap"

        elif _any_term(
            DIRECT_ACTIVITY_TERMS,
            low,
        ):
            score = 100
            reason = "Direct responsibility overlap"

        elif _any_term(
            TRANSFERABLE_ACTIVITY_TERMS,
            low,
        ):
            if _any_term(
                DOMAIN_DISTANCE_TERMS,
                low,
            ):
                score = 40
                reason = "Transferable task in a different domain"
            else:
                score = 70
                reason = "Transferable engineering task"

        elif _any_term(
            SOFT_SKILL_TERMS,
            low,
        ):
            score = 80
            reason = "General professional task"

        else:
            score = 20
            reason = "No clear evidence in CV/profile"

        details.append({
            "text": phrase,
            "score": score,
            "weight": 1.0,
            "reason": reason,
        })

    if not details:
        return 0, []

    return (
        _weighted_score(
            details
        ),
        details,
    )


def _role_fit(title):
    low = (title or "").lower()

    for role in GOOD_ROLE_WORDS:
        if role in low:
            return 100

    generic = [
        "engineer",
        "ingenieur",
        "tester",
        "testing",
        "validation",
        "verification",
        "requirements",
        "system",
        "entwicklung",
    ]

    if any(
        term in low
        for term in generic
    ):
        return 70

    return 30


def evaluate_fit(
    title,
    description,
    requirements=None,
    tasks=None,
):
    requirements = requirements or []
    tasks = tasks or []

    (
        requirement_fit,
        core_fit,
        requirement_details,
    ) = evaluate_requirements(
        requirements,
        description,
    )

    (
        responsibility_fit,
        responsibility_details,
    ) = evaluate_responsibilities(
        tasks
    )

    role_fit = _role_fit(
        title
    )

    overall = round(
        requirement_fit * 0.80
        + responsibility_fit * 0.15
        + role_fit * 0.05
    )

    overall = max(
        0,
        min(
            100,
            overall,
        )
    )

    all_text = " ".join([
        title or "",
        description or "",
        " ".join(requirements),
        " ".join(tasks),
    ])

    detected = detected_skill_scores(
        all_text
    )

    matched = sorted(
        detected.keys()
    )

    warnings = []

    for skill, value in detected.items():
        if (
            value["required_level"]
            > value["candidate_level"]
        ):
            warnings.append(
                "⚠️ "
                + skill
                + ": job appears to request "
                + LEVEL_NAMES[
                    value["required_level"]
                ]
                + "; Arash profile: "
                + LEVEL_NAMES[
                    value["candidate_level"]
                ]
            )

    uncertain_details = [
        item
        for item in requirement_details
        if item.get("category")
        in {
            "uncertain-technical",
            "unclassified",
        }
    ]

    strong_mismatches = [
        item
        for item in requirement_details
        if item.get("core")
        and item.get("weight", 0) >= 4
        and item.get("score", 100) <= 25
    ]

    normal_pass = (
        requirement_fit
        >= MIN_MATCH_PERCENT
        and core_fit >= 50
        and overall >= MIN_MATCH_PERCENT
    )

    # If some requirement text is outside our definitions, uncertainty alone
    # must not reject the job. Keep/post it unless there is a clear known core
    # mismatch. Hard filters such as >3 years, German C1+, contract and
    # location are handled before this matcher.
    fail_open = (
        bool(uncertain_details)
        and not strong_mismatches
        and not normal_pass
    )

    if fail_open:
        overall = max(
            overall,
            MIN_MATCH_PERCENT,
        )

        warnings.append(
            "⚠️ Some requirement text could not be classified confidently; "
            "kept for Telegram review because no clear core mismatch was found"
        )

    gates_pass = (
        normal_pass
        or fail_open
    )

    breakdown = {
        "requirements": requirement_fit,
        "core_requirements": core_fit,
        "responsibilities": responsibility_fit,
        "role": role_fit,
        "overall": overall,
        "gates_pass": gates_pass,
        "fail_open": fail_open,
        "uncertain_requirements": len(uncertain_details),
        "strong_mismatches": len(strong_mismatches),
        "requirement_details": requirement_details,
        "responsibility_details": responsibility_details,
    }

    return (
        overall,
        matched,
        warnings,
        breakdown,
    )


# ============================================================
# EXPERIENCE
# ============================================================

def extract_experience_years(text):
    low = (text or "").lower()
    values = []

    range_patterns = [
        r"(\d+)\s*(?:-|–|—|to|bis)\s*(\d+)\s*years?",
        r"(\d+)\s*(?:-|–|—|bis)\s*(\d+)\s*jahre",
    ]

    for pattern in range_patterns:
        for first, second in re.findall(
            pattern,
            low,
        ):
            values.extend([
                int(first),
                int(second),
            ])

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
        for value in re.findall(
            pattern,
            low,
        ):
            try:
                values.append(
                    int(value)
                )
            except Exception:
                pass

    more_than = [
        r"more than\s+(\d+)\s+years?",
        r"over\s+(\d+)\s+years?",
        r"mehr als\s+(\d+)\s+jahre",
    ]

    for pattern in more_than:
        for value in re.findall(
            pattern,
            low,
        ):
            try:
                values.append(
                    int(value) + 1
                )
            except Exception:
                pass

    if not values:
        return None

    return max(
        values
    )


def extract_candidate_experience_years(
    requirements,
    description,
):
    """
    Prefer explicit candidate requirement bullets. If LinkedIn fails to
    expose a Requirements section, fall back to year expressions only when
    the surrounding text clearly refers to the candidate, not the employer.
    """
    req_text = " ".join(
        clean(item)
        for item in (requirements or [])
        if clean(item)
    )

    if req_text:
        return extract_experience_years(
            req_text
        )

    text = clean(
        description
    )

    if not text:
        return None

    candidate_cues = [
        "you ",
        "your ",
        "bring ",
        "you bring",
        "you have",
        "must ",
        "required",
        "requirement",
        "who you are",
        "qualification",
        "experience",
        "du ",
        "dein ",
        "deine ",
        "sie ",
        "ihr ",
        "ihre ",
        "bringst",
        "hast ",
        "erfahrung",
        "kenntnisse",
        "qualifikation",
        "profil",
    ]

    employer_cues = [
        "we have been",
        "has been",
        "have been",
        "for over",
        "for more than",
        "founded",
        "since ",
        "company",
        "unternehmen",
        "seit ",
        "besteht seit",
        "am markt",
        "providing services",
        "serving customers",
    ]

    # Capture every year expression with local context.
    year_patterns = [
        r"\d+\s*\+\s*(?:years?|jahre)",
        r"(?:more than|over|at least|minimum(?: of)?|mindestens|mehr als)\s+\d+\s*(?:years?|jahre)",
        r"\d+\s*(?:-|–|—|to|bis)\s*\d+\s*(?:years?|jahre)",
        r"\d+\s*(?:years?|jahre)\s+(?:of\s+)?experience",
        r"\d+\s+jahre\s+berufserfahrung",
        r"\d+\s+jährige\s+berufserfahrung",
    ]

    candidate_chunks = []

    low = text.lower()

    for pattern in year_patterns:
        for match in re.finditer(
            pattern,
            low,
        ):
            start = max(
                0,
                match.start() - 180,
            )

            end = min(
                len(text),
                match.end() + 180,
            )

            chunk = text[
                start:end
            ]

            chunk_low = chunk.lower()

            has_candidate_cue = any(
                cue in chunk_low
                for cue in candidate_cues
            )

            has_employer_cue = any(
                cue in chunk_low
                for cue in employer_cues
            )

            # Candidate wording wins when explicit ("you bring 10+ years").
            explicit_candidate = any(
                cue in chunk_low
                for cue in [
                    "you bring",
                    "you have",
                    "must have",
                    "required",
                    "who you are",
                    "du hast",
                    "du bringst",
                    "sie haben",
                    "ihr profil",
                ]
            )

            if (
                has_candidate_cue
                and (
                    explicit_candidate
                    or not has_employer_cue
                )
            ):
                candidate_chunks.append(
                    chunk
                )

    if not candidate_chunks:
        return None

    return extract_experience_years(
        " ".join(
            candidate_chunks
        )
    )


def experience_status(required_years):
    if required_years is None:
        return (
            False,
            "Not explicitly stated",
        )

    if (
        required_years
        > MAX_REQUIRED_EXPERIENCE_YEARS
    ):
        return (
            True,
            f"Requires {required_years}+ years; "
            f"maximum accepted is {MAX_REQUIRED_EXPERIENCE_YEARS}",
        )

    return (
        False,
        "Within accepted experience range",
    )


# ============================================================
# LANGUAGE
# ============================================================

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
        if re.search(
            pattern,
            low,
        ):
            return (
                True,
                "German native / Muttersprache explicitly required",
                -100,
            )

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
    ]

    for pattern in c_patterns:
        if re.search(
            pattern,
            low,
        ):
            return (
                True,
                "German C1/C2/fluent required; current level B1 — rejected",
                -100,
            )

    very_good_patterns = [
        r"sehr gute deutschkenntnisse",
        r"sehr gutes deutsch",
        r"very good german",
    ]

    for pattern in very_good_patterns:
        if re.search(
            pattern,
            low,
        ):
            return (
                False,
                "⚠️ Very good German requested, but no explicit C1/C2 level; current level B1",
                -5,
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
            low,
        ):
            return (
                False,
                "⚠️ German B2 requested; current level B1",
                -5,
            )

    b1_patterns = [
        r"german.{0,40}\bb1\b",
        r"deutsch.{0,40}\bb1\b",
        r"\bb1\b.{0,40}german",
        r"\bb1\b.{0,40}deutsch",
    ]

    for pattern in b1_patterns:
        if re.search(
            pattern,
            low,
        ):
            return (
                False,
                "German B1 requested; matches current level",
                0,
            )

    return (
        False,
        "No explicit German level detected",
        0,
    )


# ============================================================
# CONTRACT
# ============================================================

def contract_status(
    criteria,
    description,
):
    values = []

    for key, value in (
        criteria or {}
    ).items():
        key_low = str(
            key
        ).lower()

        if any(
            term in key_low
            for term in [
                "employment",
                "beschäftigungsart",
                "beschaeftigungsart",
                "anstellungsart",
                "contract",
                "vertrag",
            ]
        ):
            values.append(
                str(value)
            )

    full = (
        " ".join(values)
        + " "
        + (description or "")
    ).lower()

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
        if re.search(
            pattern,
            full,
        ):
            return (
                True,
                "Non-permanent or non-full-time contract detected",
            )

    positive_patterns = [
        r"\bfull[- ]time\b",
        r"\bvollzeit\b",
        r"\bpermanent\b",
        r"\bunbefristet\b",
    ]

    if any(
        re.search(
            pattern,
            full,
        )
        for pattern in positive_patterns
    ):
        return (
            False,
            "Permanent/full-time compatible",
        )

    return (
        False,
        "Contract type not stated",
    )


# ============================================================
# LOCATION
# ============================================================

def location_status(
    location,
    description,
):
    location_low = (
        location
        or ""
    ).lower()

    full = (
        (location or "")
        + " "
        + (description or "")
    ).lower()

    for city in MUNICH_AREA:
        if _term_present(
            city,
            location_low,
        ):
            return (
                True,
                "Onsite/hybrid within accepted Munich ~150 km area",
            )

    for city in SPECIAL_ONSITE_EXCEPTIONS:
        if _term_present(
            city,
            location_low,
        ):
            return (
                True,
                "Accepted onsite exception: Nuremberg",
            )

    negative_remote = [
        "no remote",
        "not remote",
        "kein remote",
        "nicht remote",
        "kein homeoffice",
        "keine homeoffice",
    ]

    # Outside the accepted onsite radius, only genuinely remote
    # Germany roles are accepted. Generic "home office" / hybrid
    # wording is not enough because the user does not want recurring
    # onsite travel beyond the accepted area.
    strict_remote_terms = [
        "fully remote",
        "100% remote",
        "remote germany",
        "remote within germany",
        "remote in germany",
        "deutschlandweit remote",
        "bundesweit remote",
        "work from home",
        "working from home",
    ]

    remote_found = any(
        term in full
        for term in strict_remote_terms
    )

    germany_context = any(
        term in full
        for term in [
            "germany",
            "deutschland",
            "bundesweit",
        ]
    )

    if (
        remote_found
        and germany_context
        and not any(
            phrase in full
            for phrase in negative_remote
        )
    ):
        return (
            True,
            "Fully remote in Germany",
        )

    return (
        False,
        "Onsite/hybrid location outside accepted ~150 km Munich area",
    )


def is_senior_title(title):
    low = (
        title
        or ""
    ).lower()

    return any(
        word in low
        for word in SENIOR_TITLE_WORDS
    )


def security_warnings(text):
    low = (
        text
        or ""
    ).lower()

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
        "ü2",
        "ue2",
        "ü3",
        "ue3",
    ]

    if any(
        term in low
        for term in terms
    ):
        return [
            "⚠️ Citizenship/security-clearance requirement detected"
        ]

    return []
