"""Review throughput, queue fairness, and restart safety without live services."""
import unittest
from unittest.mock import Mock, patch

from scripts import review_digest as review


def jobs(prefix, count):
    return [{"source": "linkedin", "job_id": f"{prefix}-{i}",
             "title": "Engineer", "company": "Example", "url": "https://example.invalid"}
            for i in range(count)]


class TestReviewScheduling(unittest.TestCase):
    def select_queue(self, fresh, historical):
        responses = [Mock(status_code=200), Mock(status_code=200), Mock(status_code=200)]
        responses[0].json.return_value = fresh
        responses[1].json.return_value = fresh
        responses[2].json.return_value = historical
        with patch.object(review, "_check_config"), \
             patch.object(review, "_request", side_effect=responses) as request:
            selected = review.pending_reviews()
        return selected, request

    def test_fresh_jobs_are_not_starved_by_historical_digest_backlog(self):
        fresh, historical = jobs("fresh", 25), jobs("historical", 25)
        selected, request = self.select_queue(fresh, historical)
        self.assertEqual(fresh[:20] + historical[:5], selected)
        fresh_query = request.call_args_list[0].kwargs["params"]
        self.assertEqual("eq.false", fresh_query["sent_to_telegram"])
        self.assertIn("decision_evidence->review_priority->base.desc", fresh_query["order"])
        self.assertNotEqual("*", fresh_query["select"])

    def test_spare_historical_capacity_is_given_to_fresh_jobs(self):
        fresh, historical = jobs("fresh", 25), jobs("historical", 2)
        selected, _ = self.select_queue(fresh, historical)
        self.assertEqual(25, len(selected))
        self.assertEqual(23, sum(j["job_id"].startswith("fresh") for j in selected))
        self.assertEqual(historical, [j for j in selected if j in historical])

    def test_small_fresh_queue_does_not_prevent_historical_progress(self):
        fresh, historical = jobs("fresh", 2), jobs("historical", 25)
        selected, _ = self.select_queue(fresh, historical)
        self.assertEqual(fresh + historical[:23], selected)

    def test_job_moving_between_queries_is_reviewed_only_once(self):
        fresh, historical = jobs("fresh", 25), jobs("historical", 24)
        selected, _ = self.select_queue(fresh, [fresh[0]] + historical)
        self.assertEqual(25, len(selected))
        self.assertEqual(1, selected.count(fresh[0]))

    def test_time_budget_leaves_unprocessed_jobs_untouched(self):
        rows = jobs("fresh", 2)
        with patch.object(review, "pending_reviews", return_value=rows), \
             patch.object(review.time, "monotonic", side_effect=[0, 0, 301]), \
             patch.object(review.time, "sleep") as sleep, \
             patch.object(review, "review", return_value=("reject", {"reason": "hard filter"}, None)) as evaluate, \
             patch.object(review, "record_decision") as record, \
             patch.object(review, "update_job") as update, \
             patch.object(review, "notify_job_once") as notify:
            review.main()
        evaluate.assert_called_once_with(rows[0])
        record.assert_called_once()
        update.assert_called_once()
        self.assertEqual(rows[0]["job_id"], update.call_args.args[1])
        notify.assert_not_called()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
