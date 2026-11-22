"""Source HTTP health without credentials, response bodies or Telegram chatter."""
import atexit
from collections import Counter
import json
import os
import time
from urllib.parse import urlsplit
import requests
from functools import wraps

_state = {}

def record_counts(**counts):
    _state.setdefault("counts", {}).update(counts)

def instrument_collectors(namespace):
    for name, collector in list(namespace.items()):
        if not name.startswith("fetch_") or not callable(collector):
            continue
        def wrap(function, label):
            @wraps(function)
            def collect(*args, **kwargs):
                started = time.monotonic()
                before = _state.get("errors", 0)
                result = None
                try:
                    result = function(*args, **kwargs)
                    return result
                finally:
                    _state.setdefault("sources", []).append({"source": label, "jobs": len(result) if isinstance(result, list) else None, "seconds": round(time.monotonic() - started, 2), "http_errors": _state.get("errors", 0) - before})
            return collect
        namespace[name] = wrap(collector, name)


def start():
    started = time.monotonic()
    counters = Counter()
    original = requests.sessions.Session.request

    def request(self, method, url, *args, **kwargs):
        host = urlsplit(url).hostname or "unknown"
        # Database and Telegram URLs can contain tokens; never record their paths.
        try:
            response = original(self, method, url, *args, **kwargs)
            counters[(host, str(response.status_code))] += 1
            if response.status_code >= 400:
                _state["errors"] = _state.get("errors", 0) + 1
            return response
        except requests.RequestException:
            counters[(host, "network_error")] += 1
            _state["errors"] = _state.get("errors", 0) + 1
            raise

    requests.sessions.Session.request = request

    def finish():
        summary = {**_state, "version": "trial-v1", "commit": os.getenv("GITHUB_SHA", "local"),
                   "duration_seconds": round(time.monotonic() - started, 2),
                   "http": [{"host": host, "status": status, "count": count} for (host, status), count in sorted(counters.items())]}
        with open("run-metrics.json", "w") as output:
            json.dump(summary, output, indent=2)
        errors = sum(count for (_, status), count in counters.items() if status == "network_error" or int(status) >= 400)
        if errors:
            print(f"::warning::Source/service HTTP errors: {errors}; inspect run-metrics.json")
        path = os.getenv("GITHUB_STEP_SUMMARY")
        if path:
            with open(path, "a") as output:
                output.write("### Radar trial-v1\n\n" + f"Duration: {summary['duration_seconds']}s; HTTP errors: {errors}\n\n| Host | HTTP status | Requests |\n|---|---|---|\n")
                for item in summary["http"]:
                    output.write(f"| {item['host']} | {item['status']} | {item['count']} |\n")
                output.write("\nStage totals: " + json.dumps(summary.get("counts", {})) + "\n")
                if summary.get("sources"):
                    output.write("\n| Source | Jobs returned | Seconds | HTTP errors |\n|---|---|---|---|\n")
                    for item in summary["sources"]:
                        output.write(f"| {item['source']} | {item['jobs']} | {item['seconds']} | {item['http_errors']} |\n")
    atexit.register(finish)
