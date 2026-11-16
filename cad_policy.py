"""Conservative exclusion for required hands-on CAD design."""
import re
import unicodedata

_TOOL = re.compile(r'\b(?:[23]d[- ]?)?cad\b|\b(?:catia|solid\s*works|inventor|autocad|creo|siemens\s+nx|unigraphics)\b')
_DESIGN = re.compile(r'\bkonstruktion\b|\bkonstruktionserfahrung\b|\bmodellier\w*|\b(?:designing|drafting|modelling|modeling|mechanical design|[23]d design|cad design)\b|\b(?:erstell\w*|anfertig\w*|creat\w*|develop\w*)\b.{0,65}\b(?:model\w*|zeichnung\w*|drawings?)\b')
_EXPERIENCE = re.compile(r'\b(?:erfahrung\w*|experience|background|praxis\w*|nachweis\w*|proven|fundiert\w*|mehrjährig\w*|sicher\w*|proficien\w*|required|mandatory|must|zwingend|vorausgesetzt|erforderlich)\b')
_OPTIONAL = re.compile(r'\b(?:idealerweise|ideally|preferred|preferably|wünschenswert|von vorteil|advantage|desirable|optional|a plus|nice[- ]to[- ]have|kein muss|not required|nicht erforderlich)\b')
_READ = re.compile(r'\b(?:lesen|reading|read|interpret\w*|view\w*|betrachten|prüfen|reviewing)\b')
_STRONG = re.compile(r'\b(?:fundiert\w*|mehrjährig\w*|proven|required|mandatory|must|zwingend|vorausgesetzt|erforderlich)\b')
REASON = "Mandatory hands-on CAD design experience"


def cad_block_reason(requirements=(), description=""):
    lines = [(line, True) for line in requirements or ()]
    lines += [(line, False) for line in re.split(r'[\n;]+|(?<=[.!?])\s+', description or '')]
    for raw, structured in lines:
        line = unicodedata.normalize("NFKC", raw).casefold()
        for clause in line.split(';'):
            design, tool = _DESIGN.search(clause), _TOOL.search(clause)
            if not design or not tool or not _EXPERIENCE.search(clause) or _READ.search(clause):
                continue
            if not structured and not _STRONG.search(clause):
                continue
            opt = _OPTIONAL.search(clause)
            if opt:
                # A trailing preference for a specific tool leaves the preceding
                # design requirement intact (but not when CAD itself is optional).
                prefix = clause[:opt.start()].rstrip()
                if not (design.end() <= len(prefix)
                        and re.search(r',\s*$', prefix)
                        and re.match(r'\s+(?:mit|with|using)\s+', clause[opt.end():])
                        and not re.match(r'\s*[23]d[- ]?cad\b|\s*cad\b', clause[tool.start():])):
                    continue
            return REASON
    return None
