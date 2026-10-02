"""Mark completed production Actions unsuccessful if job-source processing silently failed."""
import re
import sys
from pathlib import Path


def assess_log(source, log):
    if source == "bmw":
        match = re.search(r"TOTAL BMW JOBS READ:\s*(\d+)", log)
        count = int(match.group(1)) if match else 0
        failures = re.search(r"Supabase sync failures:\s*(\d+)", log)
        good = (count > 0
                and "BMW SUPABASE BRIDGE: SUCCESS" in log
                and failures is not None
                and int(failures.group(1)) == 0)
        return good, f"BMW jobs read={count}; bridge success={'BMW SUPABASE BRIDGE: SUCCESS' in log}"
    if source == "linkedin":
        match = re.search(r"TOTAL UNIQUE LINKEDIN JOBS:\s*(\d+)", log)
        count = int(match.group(1)) if match else 0
        search_http = re.findall(r"^\s*HTTP:\s*(\d+)", log, re.MULTILINE)
        good = (
            count > 0
            and len(search_http) == 5
            and all(code == "200" for code in search_http)
            and "LINKEDIN + SUPABASE SUMMARY" in log
        )
        return good, f"LinkedIn unique jobs={count}; search HTTP statuses={search_http}"
    raise ValueError("Unknown live source")


def main():
    source, filename = sys.argv[1:3]
    success, description = assess_log(source, Path(filename).read_text(encoding="utf-8"))
    print("Live monitor health:", description)
    if not success:
        raise SystemExit(source + " source scan incomplete/failed; do not mark Action successful")


if __name__ == "__main__":
    main()
