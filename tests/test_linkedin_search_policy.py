"""Pure tests for LinkedIn search scope and rate-limit policy."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import linkedin_monitor


class TestLinkedInSearchPolicy(unittest.TestCase):
    def test_local_search_is_munich_scoped_with_radius(self):
        params = linkedin_monitor.build_search_params("ADAS Test Engineer")
        self.assertEqual(params["location"], "Munich, Bavaria, Germany")
        self.assertEqual(params["distance"], 100)
        self.assertNotIn("f_WT", params)
        self.assertEqual(params["f_TPR"], "r86400")
        self.assertEqual(params["sortBy"], "DD")

    def test_remote_search_is_germany_wide_and_remote_filtered(self):
        params = linkedin_monitor.build_search_params(
            "System Integration Engineer",
            remote_only=True,
        )
        self.assertEqual(params["location"], "Germany")
        self.assertEqual(params["f_WT"], "2")
        self.assertNotIn("distance", params)

    def test_retry_after_is_honored_and_capped(self):
        response = SimpleNamespace(headers={"Retry-After": "120"})
        self.assertEqual(
            linkedin_monitor.retry_after_seconds(response),
            linkedin_monitor.RATE_LIMIT_RETRY_MAX_SECONDS,
        )

    def test_retry_after_falls_back_when_missing_or_invalid(self):
        response = SimpleNamespace(headers={"Retry-After": "not-a-number"})
        self.assertEqual(
            linkedin_monitor.retry_after_seconds(response),
            linkedin_monitor.RATE_LIMIT_RETRY_DEFAULT_SECONDS,
        )

    @patch("linkedin_monitor.get_job_record")
    def test_remote_filter_rechecks_old_pre_detail_location_rejection(self, get_record):
        get_record.return_value = {
            "status": "rejected_location@" + linkedin_monitor.MATCHER_REVISION,
            "sent_to_telegram": False,
            "posted_at": "2026-10-05",
        }
        job = {
            "job_id": "123",
            "posted": "2026-10-05",
            "remote_search": True,
        }
        self.assertFalse(linkedin_monitor.already_seen(job))

    @patch("linkedin_monitor.get_job_record")
    def test_remote_location_rejection_is_not_rechecked_forever(self, get_record):
        get_record.return_value = {
            "status": "rejected_location_remote@" + linkedin_monitor.MATCHER_REVISION,
            "sent_to_telegram": False,
            "posted_at": "2026-10-05",
        }
        job = {
            "job_id": "123",
            "posted": "2026-10-05",
            "remote_search": True,
        }
        self.assertTrue(linkedin_monitor.already_seen(job))

    @patch("linkedin_monitor.get_job_record")
    def test_current_pending_review_is_rechecked_for_immediate_notification(self, get_record):
        get_record.return_value = {
            "status": "review_required@" + linkedin_monitor.MATCHER_REVISION,
            "sent_to_telegram": False,
            "posted_at": "2026-10-06",
        }
        job = {
            "job_id": "4458269624",
            "posted": "2026-10-06",
            "remote_search": False,
        }
        self.assertFalse(linkedin_monitor.already_seen(job))

    @patch("linkedin_monitor.get_job_record")
    def test_notified_review_is_not_rechecked_until_matcher_changes(self, get_record):
        get_record.return_value = {
            "status": "review_required_notified@" + linkedin_monitor.MATCHER_REVISION,
            "sent_to_telegram": False,
            "posted_at": "2026-10-06",
        }
        job = {
            "job_id": "4458269624",
            "posted": "2026-10-06",
            "remote_search": False,
        }
        self.assertTrue(linkedin_monitor.already_seen(job))


if __name__ == "__main__":
    unittest.main()
