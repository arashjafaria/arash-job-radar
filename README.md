# Arash Job Radar — operational runbook

## Live vs validation

| Pipeline | GitHub workflow | Schedule | Telegram job alerts |
|---|---|---|---|
| BMW | `job-radar.yml` | External five-minute dispatcher | Yes, for eligible matches |
| LinkedIn | `linkedin-radar.yml` | External five-minute dispatcher, internally gated to real scans every 15 minutes | Yes, for eligible matches |
| StepStone | `market-radar.yml` | Mondays 06:00 UTC, or safe manual dry run | **No** — dry run only |
| Indeed | No production activation | None | **No** — known HTTP 403 |
| Regression & independent source health | `quality-gates.yml` | Every relevant code change and daily 05:45 UTC | Only on daily failure |
| Second-stage review | `review-digest.yml` | Supabase dispatcher every 15 minutes | Only never-notified opportunities, through permanent reservations |

The legacy `public_sources_monitor.py` is deliberately absent from the BMW workflow and is also disabled by default. Do **not** re-enable it as a shortcut: it is an obsolete second implementation.

## Safe validation and release procedure

1. Run `python -m unittest discover -s tests -v` before proposing or merging matching changes. The initial offline baseline contains **45 explicitly synthetic scenarios** plus **two reviewed actual vacancies**. This is not an accuracy benchmark.
2. Check the GitHub Actions quality-gate result for the exact commit. No live APIs, Supabase writes, or Telegram job notifications occur in these regression tests.
3. The independent weekly StepStone workflow always uses `MARKET_DRY_RUN=1`. It archives `market_scan.log`, `market_health.json`, and `market_audit.jsonl`. It fails if it cannot extract any actual job descriptions. The simulated `sent` count means **potential matches, never notifications delivered**.
4. Manually label a diverse set of **40–50 real advertisements**, spanning relevant, adjacent, clearly unrelated and missing-information jobs. Evaluate false positives and false negatives separately. The repository does not yet contain that completed real-world benchmark.
5. **Do not** switch `MARKET_DRY_RUN` to `0` or add Indeed to `MARKET_SOURCES` until the benchmark passes, access is permitted/reliable, and deployment is separately approved.
6. Second-stage review fetches a fresh description, retries section extraction, and persists `apply`, `reject`, or `manual` with a specific reason. Unclassified requirements remain manual; a retry does not invent CV evidence.

Second-stage review handles up to 25 jobs per run within a five-minute processing
budget, spacing description requests by 2.5 seconds. Twenty slots prioritize
never-notified vacancies and five reserve progress for already-notified reviews.
Within the twenty, eighteen rank existing matcher evidence and two guarantee
progress for the longest-waiting vacancies. Priority is not a match percentage:
verified core fit contributes up to 25 points, task fit 35, requirement fit 15,
and classification coverage 10. Core/requirement scores are discounted by
coverage. Publication freshness adds up to 15 points (24h: 15; 72h: 10; seven
days: 5), and waiting adds up to ten points. Unknown/future publication dates
get no freshness boost, not a rejection. There is no new age-based exclusion.
Priority is stored inside existing decision evidence in the same write, with
no extra source request. The queue reads compact metadata for at most 100
ranked, 25 oldest, and 25 historical candidates; no full descriptions are
downloaded for sorting. Unused slots are shared. Jobs outside the batch or
time budget stay queued for the next 15-minute run. There is no daily review cap.
After deploying the workflow, run `scripts/review_schedule.sql` in the existing
Supabase project to install/update its named dispatcher. GitHub workflow
concurrency prevents overlapping review workers; notification reservations are
unchanged.

## Release prerequisite: database migration

Before merging/deploying this change, pause the external dispatchers and wait for
existing BMW, LinkedIn, and review runs to finish. Execute
`migrations/20261011_decisions_and_notifications.sql` in the existing Supabase
SQL Editor, then deploy and resume dispatchers. The migration is idempotent and
imports all tracked `sent`, `sent_to_telegram=true`, and `review_digest_sent*`
records into permanent notification history. Do not clear this table on matcher
updates, reposts, or job-table cleanup. Code fails closed if reservation RPCs or
evidence columns are missing; it will not fall back to unprotected sending.

Historical Telegram posts whose database delivery marker was already lost
cannot be reconstructed automatically. Reconcile known missing markers before
deploying if such posts exist. No live Supabase migration is performed by CI.

Every job producer, including the disabled legacy collector, now reserves the
job before a single Telegram message. A second-stage `APPLY` decision for an
already-digested job changes the database decision only. Reposts may be matched
again, but they never reset the original job's notification reservation.

Reservations use a PostgreSQL transaction lock across sources and permanent
source/job-ID history, canonical URLs, and normalized company/title/location
identity. Conservative identity matching may suppress a distinct vacancy with
the same role at the same employer and place. Arbitrarily renamed duplicates
cannot be guaranteed detectable without a shared employer requisition ID.

Telegram has no idempotency key. This is **at-most-once attempted delivery**, not
guaranteed delivery: timeouts, interrupted runs, or an unavailable outcome write
leave the reservation intact and may lose an alert. Never automatically release
or retry those reservations. `notification_status` distinguishes `claimed`,
`delivered`, `uncertain`, and `suppressed`; it is independent of matching decisions.

The quality workflow includes a disposable PostgreSQL 16 database and exercises
the actual migration/RPCs, including competing concurrent claims. For local DB
tests, set `RADAR_TEST_DATABASE_URL` to an **empty disposable database** and install
`psycopg[binary]`. The tests refuse to overwrite an existing `arash_jobs` table.

## Health, reliability and known limits

- Required native/fluent/C1/C2 German is a hard rejection in initial and second-stage review. Optional/preferred German does not trigger it. English fluency and English CEFR levels are not assigned to German. B2 and unspecified "very good German" retain the existing warning policy. Notification reservations are unchanged.

- BMW and LinkedIn workflows now fail when actual source activity is missing or their evidence of a successful scan is absent. The separate daily quality workflow checks recent production runs and issues at most one scheduled health alert per day.
- LinkedIn local discovery is scoped to Munich with a 100-mile (~161 km) radius so Germany-wide first-page results do not crowd local vacancies out. A separate Germany-wide remote-filter sample runs once per hour.
- LinkedIn HTTP 429 handling now honors `Retry-After` when numeric, retries once with a capped wait, and stops the local scan after two persistent 429 responses. A single persistent 429 remains degraded-but-usable; broader blocking is a hard failure and triggers a Telegram health alert.
- Supabase stores matching decisions and evidence independently of delivery history. All job producers use a permanent transactional notification reservation.
- Every tracked job ID is reserved before Telegram is contacted; matching updates never erase notification history. Long job messages are compacted to one message with a vacancy link, avoiding repeat multipart posts after partial failure.
- Real websites may change markup, apply rate limits, or restrict automated access. A green workflow means the health gate passed; it does not establish that matching recommendations are perfect.
- Python dependencies: `pip install -r requirements.txt`. StepStone dry runs also require Playwright's Chromium runtime. The shared matcher revision lives in `profile.py`.

## Credentials

GitHub Actions secrets used by the live/dry-run workflows: `BOT_TOKEN`, `CHAT_ID`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`. GitHub provides the daily status check with its normal `GITHUB_TOKEN`. Never store credentials in the repository or its public Actions artifacts.
