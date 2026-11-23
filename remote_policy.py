"""Explicit remote/mobile-work wording overrides onsite geography only."""
import re

_OFFER = re.compile(
    r"\bremote(?:ly)?\b(?![\s-]+(?:control|sensing|debugging|monitoring|access|desktop|diagnostics|operation))"
    r"|\bmobil(?:e[snr]?|er)?[\s-]+arbeit(?:en)?\b|\bmobilarbeit\b"
    r"|\bhome[\s-]*office\b|\bwork(?:ing)?\s+from\s+home\b", re.I)
_NEGATIVE = re.compile(
    r"\b(?:no|not|kein\w*|nicht)\b.{0,45}(?:remote|home[\s-]*office|mobil\w*\s+arbeit|mobilarbeit|work\w*\s+from\s+home)"
    r"|(?:remote|home[\s-]*office|mobil\w*\s+arbeit|mobilarbeit).{0,30}\b(?:not\s+(?:possible|available|offered)|nicht\s+möglich|ausgeschlossen)\b", re.I)


def offers_remote_work(*texts):
    for text in texts:
        for clause in re.split(r"[\n;.!?]+", str(text or "")):
            if _OFFER.search(clause) and not _NEGATIVE.search(clause):
                return True
    return False
