"""Fail CI-style live validation when the source was blocked or produced no usable sample."""
import json
import re
import sys
from pathlib import Path


def parse_health(log):
    # Count a dry-run "sent" as a potential notification, not a real send.
    if not re.search(r"Dry run:\s*True", log):
        raise ValueError("Validation was not in dry-run mode; refusing to summarize.")
    match = re.search(
        r"STEPSTONE\s*\|\s*candidates:\s*(\d+)\s*\|\s*checked:\s*(\d+)\s*\|\s*sent:\s*(\d+)",
        log,
    )
    if not match:
        raise ValueError("StepStone summary absent; cannot distinguish a healthy scan from a failed scan.")
    candidates, checked, potential_matches = map(int, match.groups())
    result = {
        "source": "stepstone",
        "dry_run": True,
        "candidates": candidates,
        "checked": checked,
        "potential_matches_not_sent": potential_matches,
        "healthy": candidates > 0 and checked > 0,
    }
    return result


def main():
    data = parse_health(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path("market_health.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("Live StepStone validation health:", json.dumps(data))
    if not data["healthy"]:
        raise SystemExit("Live StepStone validation failed: zero candidates/details.")


if __name__ == "__main__":
    main()
