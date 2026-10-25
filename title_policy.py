"""User title exclusions, applied to titles only (never to degree requirements)."""
import re

from profile import EXCLUDE_WORDS


TITLE_RULES = (
    (r'\bit\b', 'IT title excluded by user'),
    (r'\belectrical[\s-]+engineers?\b|\belektroingenieur\w*\b', 'Electrical Engineer title excluded by user'),
    (r'\bmechanical[\s-]+engineers?\b|\bmaschinenbauingenieur\w*\b', 'Mechanical Engineer title excluded by user'),
    (r'\b(?:bachelorand\w*|masterand\w*)\b', 'Student thesis position excluded'),
)


def excluded_title_reason(title):
    title = title or ''
    for pattern, reason in TITLE_RULES:
        if re.search(pattern, title, re.I):
            return reason
    if any(word.lower() in title.lower() for word in EXCLUDE_WORDS):
        return 'Excluded student/training title'
    return None
