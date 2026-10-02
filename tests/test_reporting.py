"""Regression checks for scheduling safety, review queue, and reporting."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import linkedin_monitor as linkedin
import market_monitor as market
import public_sources_monitor as legacy
from scripts import market_health
from scripts import weekly_report


class TestLiveHealthParsing(unittest.TestCase):
    VALID = "Dry run: True\\nSTEPSTONE | candidates: 25 | checked: 12 | sent: 2\\n"

    def test_valid_dry_run(self):
        data = market_health.parse_health(self.VALID)
        self.assertTrue(data["healthy"])
        self.assertEqual(25, data["candidates"])
        self.assertEqual(12, data["checked"])
        self.assertEqual(2, data["potential_matches_not_sent"])

    def test_live_telegram_run_cannot_masquerade_as_validation(self):
        with self.assertRaises(ValueError):
            market_health.parse_health(self.VALID.replace("True", "False"))

    def test_missing_summary_is_a_failure(self):
        with self.assertRaises(ValueError):
            market_health.parse_health("Dry run: True\nStepStone HTTP 403")

    def test_zero_candidates_is_unhealthy(self):
        result = market_health.parse_health(
            "Dry run: True\nSTEPSTONE | candidates: 0 | checked: 0 | sent: 0"
        )
        self.assertFalse(result["healthy"])


class TestReviewQueue(unittest.TestCase):
    def test_weekly_summary_labels_dry_run_properly(self):
        health = {"candidates": 25, "checked": 12, "potential_matches_not_sent": 2, "healthy": True}
        rows = [{"title": "ECU tester", "company": "Example", "source": "linkedin", "url": "https://example.invalid/job/1"}]
        message = weekly_report.build_report(health, rows)
        self.assertIn("DRY RUN ONLY", message)
        self.assertIn("Potential matches: 2", message)
        self.assertIn("ECU tester", message)

    def test_review_digest_marks_records_only_after_success(self):
        health = {"candidates": 10, "checked": 10, "potential_matches_not_sent": 0, "healthy": True}
        rows = [{"source": "linkedin", "job_id": "x", "title": "Engineer", "url": "https://example.invalid"}]
        reply = MagicMock()
        with (
            patch.dict(os.environ, {"MARKET_DRY_RUN": "1", "BOT_TOKEN": "dummy", "CHAT_ID": "dummy"}),
            patch.object(weekly_report.Path, "read_text", return_value=json.dumps(health)),
            patch.object(weekly_report, "query_reviews", return_value=rows),
            patch.object(weekly_report.requests, "post", return_value=reply) as send,
            patch.object(weekly_report, "update_job") as update,
        ):
            weekly_report.main()
        reply.raise_for_status.assert_called_once()
        send.assert_called_once()
        update.assert_called_once()

    def test_legacy_collector_stays_off_without_explicit_opt_in(self):
        with (
            patch.dict(os.environ, {"ENABLE_LEGACY_PUBLIC_SOURCES": "0"}),
            patch.object(legacy, "stepstone_search") as stepstone,
            patch.object(legacy, "indeed_search") as indeed,
        ):
            legacy.main()
        stepstone.assert_not_called()
        indeed.assert_not_called()

    def test_matcher_review_queue_does_not_notify_market_telegram(self):
        candidate = {"source": "stepstone", "source_name": "STEPSTONE", "job_id": "fake", "url": "https://example.invalid"}
        details = {
            "title": "System Engineer", "company": "Example GmbH",
            "location": "Munich", "date_posted": "", "employment_type": "FULL_TIME",
            "description": "Proprietary technologies", "requirements": ["Unknown proprietary stack"],
            "tasks": ["Coordinate projects"], "other": [],
        }
        with (
            patch.object(market, "get_job_details", return_value=details),
            patch.object(market, "cv_location_status", return_value=(True, "Munich")),
            patch.object(market, "cv_extract_candidate_experience_years", return_value=None),
            patch.object(market, "cv_experience_status", return_value=(False, "Not specified")),
            patch.object(market, "cv_contract_status", return_value=(False, "FULL_TIME")),
            patch.object(market, "cv_german_requirement", return_value=(False, "No level", 0)),
            patch.object(market, "cv_evaluate_fit", return_value=(0, [], [], {"review_required": True, "gates_pass": False})),
            patch.object(market, "remember") as remember,
            patch.object(market, "send_telegram") as notify,
        ):
            result = market.evaluate_candidate(MagicMock(), candidate)
        self.assertFalse(result)
        self.assertEqual("review_required", remember.call_args.args[2])
        notify.assert_not_called()

    def test_old_review_is_rechecked_when_matcher_changes(self):
        with (
            patch.object(linkedin, "TEST_MODE", False),
            patch.object(linkedin, "get_job_record", return_value={"status": "review_digest_sent@2026-09-30-c", "sent_to_telegram": False}),
        ):
            self.assertFalse(linkedin.already_seen({"job_id": "old", "posted": ""}))

    def test_current_review_does_not_repeat_every_five_minutes(self):
        with (
            patch.object(linkedin, "TEST_MODE", False),
            patch.object(linkedin, "get_job_record", return_value={"status": "review_required@2026-10-02-a", "sent_to_telegram": False}),
        ):
            self.assertTrue(linkedin.already_seen({"job_id": "new", "posted": ""}))


if __name__ == "__main__":
    unittest.main()
