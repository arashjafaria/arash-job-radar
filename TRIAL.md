# Two-week optimization trial

Baseline: `baseline/pre-optimization-2026-11-22`, commit `1107a76f13cec5f2c5cba2baeb4d1fce5386c7ae`.
Trial starts when this PR is merged into main; observe for 14 days. Existing sources, search terms, radius, exclusions, thresholds, schedules and Telegram destination stay configured as before. Only the new main runs production.

Changes: verified responsibilities now contribute to queue order; saved version-1 priorities are recalculated from existing evidence, without new source requests. A few direct German activity spellings are recognized. LinkedIn history is fetched in batches of 100 instead of one request per card; permanent delivery claims are still checked at sending time.

Monitor Actions run summaries and the `radar-trial-*` artifacts (30-day retention). Metrics include commit, runtime, HTTP status counts and LinkedIn stage totals. Gated LinkedIn dispatches do not produce a scan artifact. Existing ALTEN/FERCHAU audit artifacts and health checks remain enabled. Evaluate fit, irrelevant alerts, review load, source failures, and time from publication to receipt; compare similar weekdays and treat market volume changes separately.

Rollback: revert this optimization PR with a new GitHub revert PR, run the same quality gates, then merge the revert. Do not reset/delete database jobs, decision evidence, notification history, or delivery reservations. The saved baseline is code only; it is not a database restore. Baseline version remains available at the branch above.
