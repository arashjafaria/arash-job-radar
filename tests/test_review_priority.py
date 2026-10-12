"""Queue priority reuses evidence without source requests or decision overrides."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch

from decisions import record_decision
from review_priority import build_priority, queue_priority, prioritize
from scripts import review_digest

NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)


def evidence(core=90, requirements=90, tasks=90, coverage=90):
    return {"breakdown": {"core_requirements": core, "core_evidence": core > 0,
            "requirements": requirements, "responsibilities": tasks,
            "evidence_coverage_percent": coverage,
            "responsibility_details": [{"weight": 4}]}}


def row(name, base, age=0, wait=0):
    return {"source": "linkedin", "job_id": name, "title": name,
            "review_priority": {"base": base},
            "posted_at": (NOW - timedelta(hours=age)).isoformat(),
            "first_seen_at": (NOW - timedelta(hours=wait)).isoformat()}


class TestReviewPriority(unittest.TestCase):
    def test_three_day_verified_ecu_fit_beats_fresh_weak_fit(self):
        ecu = row("ECU and UDS", build_priority(evidence())["base"], age=72)
        weak = row("Generic development role", build_priority(evidence(0, 90, 20, 20))["base"])
        self.assertEqual([ecu, weak], prioritize([weak, ecu], NOW))

    def test_high_score_from_sparse_evidence_does_not_dominate(self):
        sparse = build_priority(evidence(100, 100, 50, 10))["base"]
        clear = build_priority(evidence(70, 70, 70, 85))["base"]
        self.assertGreater(clear, sparse)

    def test_unknown_task_text_cannot_manufacture_verified_task_priority(self):
        e = evidence()
        e["breakdown"]["responsibility_details"] = [{"weight": 0}] * 8
        self.assertEqual(0, build_priority(e)["components"]["task_fit"])

    def test_recency_is_capped_and_never_an_age_rejection(self):
        self.assertEqual(15, queue_priority(row("fresh", 0), NOW))
        self.assertEqual(10, queue_priority(row("two-days", 0, age=48), NOW))
        self.assertEqual(5, queue_priority(row("week", 0, age=168), NOW))
        self.assertEqual(65, queue_priority(row("older-strong", 65, age=200), NOW))

    def test_unknown_and_future_dates_get_no_freshness_boost(self):
        for date in (None, "unknown", "yesterday", (NOW + timedelta(days=1)).isoformat()):
            candidate = row("unknown-date", 30)
            candidate["posted_at"] = date
            self.assertEqual(30, queue_priority(candidate, NOW))

    def test_waiting_bonus_is_capped(self):
        self.assertEqual(40, queue_priority(row("waiting", 30, age=200, wait=1000), NOW))

    def test_legacy_missing_evidence_stays_unknown_not_rejected(self):
        self.assertFalse(build_priority({})["known"])
        self.assertEqual(15, queue_priority({"posted_at": NOW.isoformat(), "match_score": 100}, NOW))

    def test_priority_is_persisted_in_same_decision_write(self):
        e = {**evidence(), "decision": "manual", "reason": "requires verification"}
        with patch("decisions.save_decision") as save:
            record_decision("linkedin", "test", "review_required", 70, e)
        save.assert_called_once()
        self.assertEqual("manual", save.call_args.args[2])
        self.assertIn("review_priority", save.call_args.args[3])
        self.assertNotIn("review_priority", e)  # Caller evidence is not mutated.

    def test_long_waiting_jobs_outside_ranked_pool_keep_reserved_slots(self):
        high = [row(f"high-{i}", 80) for i in range(100)]
        old = [row(f"old-{i}", 0, age=200, wait=200) for i in range(25)]
        responses = [Mock(status_code=200) for _ in range(3)]
        for response, data in zip(responses, [high, old, []]):
            response.json.return_value = data
        with patch.object(review_digest, "_check_config"), \
             patch.object(review_digest, "_request", side_effect=responses), \
             patch("review_priority.datetime") as clock:
            clock.now.return_value = NOW
            clock.fromisoformat.side_effect = datetime.fromisoformat
            selected = review_digest.pending_reviews()
        self.assertEqual(25, len(selected))
        self.assertIn(old[0], selected)
        self.assertIn(old[1], selected)
        self.assertEqual(23, sum(r["job_id"].startswith("high") for r in selected))


if __name__ == "__main__":
    unittest.main()
