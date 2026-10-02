# Arash Job Radar — operational runbook

## Live vs validation

| Pipeline | GitHub workflow | Schedule | Telegram job alerts |
|---|---|---|---|
| BMW | `job-radar.yml` | External five-minute dispatcher | Yes, for eligible matches |
| LinkedIn | `linkedin-radar.yml` | External five-minute dispatcher (offset) | Yes, for eligible matches |
| StepStone | `market-radar.yml` | Mondays 06:00 UTC, or safe manual dry run | **No** — dry run only |
| Indeed | No production activation | None | **No** — known HTTP 403 |
| Regression & independent source health | `quality-gates.yml` | Every relevant code change and daily 05:45 UTC | Only on daily failure |
| Low-confidence review digest | `review-digest.yml` | Daily 16:30 UTC | At most eight queued items per digest |

The legacy `public_sources_monitor.py` is deliberately absent from the BMW workflow and is also disabled by default. Do **not** re-enable it as a shortcut: it is an obsolete second implementation.

## Safe validation and release procedure

1. Run `python -m unittest discover -s tests -v` before proposing or merging matching changes. The initial offline baseline contains **45 explicitly synthetic scenarios** plus **two reviewed actual vacancies**. This is not an accuracy benchmark.
2. Check the GitHub Actions quality-gate result for the exact commit. No live APIs, Supabase writes, or Telegram job notifications occur in these regression tests.
3. The independent weekly StepStone workflow always uses `MARKET_DRY_RUN=1`. It archives `market_scan.log`, `market_health.json`, and `market_audit.jsonl`. It fails if it cannot extract any actual job descriptions. The simulated `sent` count means **potential matches, never notifications delivered**.
4. Manually label a diverse set of **40–50 real advertisements**, spanning relevant, adjacent, clearly unrelated and missing-information jobs. Evaluate false positives and false negatives separately. The repository does not yet contain that completed real-world benchmark.
5. **Do not** switch `MARKET_DRY_RUN` to `0` or add Indeed to `MARKET_SOURCES` until the benchmark passes, access is permitted/reliable, and deployment is separately approved.
6. Review the daily low-confidence digest: unclassified requirements go to manual review rather than being treated as proof of a match or silently discarded.

## Health, reliability and known limits

- BMW and LinkedIn workflows now fail when actual source activity is missing or their evidence of a successful scan is absent. The separate daily quality workflow checks recent production runs and issues at most one scheduled health alert per day.
- Supabase stores seen/sent/review states. The revised BMW bridge retains job titles and locations for future cross-source duplicate checks. Alerts are sent only after an additional best-effort cross-source duplicate lookup.
- **Concurrent notification delivery is not fully atomic**. A rare duplicate is still possible if two sources send the same vacancy simultaneously or Telegram succeeds before a failed Supabase write. Full exactly-once delivery would require a transactional database claim/outbox design.
- Real websites may change markup, apply rate limits, or restrict automated access. A green workflow means the health gate passed; it does not establish that matching recommendations are perfect.
- Python dependencies: `pip install -r requirements.txt`. StepStone dry runs also require Playwright's Chromium runtime. The shared matcher revision lives in `profile.py`.

## Credentials

GitHub Actions secrets used by the live/dry-run workflows: `BOT_TOKEN`, `CHAT_ID`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`. GitHub provides the daily status check with its normal `GITHUB_TOKEN`. Never store credentials in the repository or its public Actions artifacts.
