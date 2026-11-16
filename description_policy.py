"""Hard exclusions based on the text of a vacancy."""
import unicodedata

from cad_policy import cad_block_reason

FPGA_REASON = "FPGA mentioned in job description"


def fpga_block_reason(*texts):
    if any("fpga" in unicodedata.normalize("NFKC", text or "").casefold()
           for text in texts):
        return FPGA_REASON
    return None


def description_block_reason(description="", requirements=(), tasks=()):
    return (fpga_block_reason(description, *(requirements or ()), *(tasks or ()))
            or cad_block_reason(requirements, description))
