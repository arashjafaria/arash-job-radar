"""Only explicit full remote work can waive the onsite city restriction."""
import re

_FULL = re.compile(
    r"\b(?:fully|full|completely|entirely|vollständig|vollstaendig|komplett|ausschließlich|ausschliesslich)[\s-]+remote\b"
    r"|\b100\s*%\s*(?:remote|home[\s-]*office|mobiles?\s+arbeiten)\b"
    r"|\b(?:remote|home[\s-]*office)\s*(?:zu\s+)?100\s*%"
    r"|\b(?:vollständig|vollstaendig|komplett|ausschließlich|ausschliesslich)\s+(?:im\s+)?home[\s-]*office\b",
    re.I)
_NEGATIVE = re.compile(
    r"\b(?:no|not|kein\w*|nicht)\b.{0,45}(?:remote|home[\s-]*office)"
    r"|(?:remote|home[\s-]*office).{0,30}\b(?:not\s+(?:possible|available|offered)|nicht\s+m(?:ö|oe)glich|ausgeschlossen)\b", re.I)
_REQUIRED_ONSITE = re.compile(
    r"\b(?:mandatory|required|regular)\s+(?:on[\s-]?site|office)\s+(?:attendance|presence|visits)"
    r"|\bmust\s+(?:work|be|attend).{0,30}(?:on[\s-]?site|in\s+(?:the|our)\s+office)"
    r"|\b(?:one|two|three|four|five|[1-5])\s+days?\s+(?:a|per|each)\s+week.{0,35}(?:office|on[\s-]?site)"
    r"|\b(?:regelmäßige?|regelmaessige?|verpflichtende?)\s+(?:präsenz|praesenz|anwesenheit|büro|buero)\w*"
    r"|\b[1-5]\s+tage?\s+(?:pro\s+)?w(?:ö|oe)ch\w*.{0,30}(?:büro|buero|vor\s+ort)", re.I)


def offers_remote_work(*texts):
    """Compatibility name: now means an explicit FULL remote offer only.

    Plain Remote, hybrid, Homeoffice and Mobiles Arbeiten nach Absprache
    never waive geography. Regular mandatory office presence also blocks it.
    """
    text = "\n".join(str(value or "") for value in texts)
    if _REQUIRED_ONSITE.search(text):
        return False
    for clause in re.split(r"[\n;.!?]+", text):
        match = _FULL.search(clause)
        if match and not _NEGATIVE.search(clause):
            if not re.match(r"[\s-]+(?:control|sensing|debugging|monitoring|access|desktop|diagnostics|operation)\b", clause[match.end():], re.I):
                return True
    return False
