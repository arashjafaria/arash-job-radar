"""Hard exclusions based on the text of a vacancy."""
import re
import unicodedata

from cad_policy import cad_block_reason

FPGA_REASON = "FPGA mentioned in job description"


PCB_REASON = "PCB design mentioned in job description"
_PCB_DESIGN = re.compile(r"\bpcb[\s\-‐‑‒–—]+design\w*\b")


def keyword_block_reason(*texts):
    normalized = [unicodedata.normalize("NFKC", text or "").casefold() for text in texts]
    if any("fpga" in text for text in normalized):
        return FPGA_REASON
    if any(_PCB_DESIGN.search(text) for text in normalized):
        return PCB_REASON
    return None


def description_block_reason(description="", requirements=(), tasks=()):
    return (keyword_block_reason(description, *(requirements or ()), *(tasks or ()))
            or cad_block_reason(requirements, description))
