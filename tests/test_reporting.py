"""Regression checks for scheduling safety, review queue, and reporting."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import linkedin_monitor as linkedin
import market_monitor as market
import public_sources_monitor as legacy
import bmw_supabase_runner as bmw_runner
import supabase_store as store
from scripts import market_health
from scripts import weekly_report
from scripts import review_digest


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
        health = {"candidates": 25, "checked": 12, "details_extracted": 9,
                  "scored": 6, "potential_matches_not_sent": 2, "healthy": True}
        message = weekly_report.build_report(health)
        self.assertIn("DRY RUN", message)
        self.assertIn("Potential matches: 2", message)
        self.assertIn("Descriptions successfully extracted: 9", message)

    def test_review_digest_marks_records_only_after_success(self):
        rows = [{"source": "linkedin", "job_id": "x", "title": "Engineer",
                 "company": "Example", "url": "https://example.invalid"}]
        reply = MagicMock()
        with (
            patch.dict(os.environ, {"BOT_TOKEN": "dummy", "CHAT_ID": "dummy"}),
            patch.object(review_digest, "pending_reviews", return_value=rows),
            patch.object(review_digest.requests, "post", return_value=reply) as send,
            patch.object(review_digest, "update_job") as update,
        ):
            review_digest.main()
        reply.raise_for_status.assert_called_once()
        send.assert_called_once()
        update.assert_called_once()

    def test_empty_review_queue_sends_nothing(self):
        with (
            patch.object(review_digest, "pending_reviews", return_value=[]),
            patch.object(review_digest.requests, "post") as send,
        ):
            review_digest.main()
        send.assert_not_called()

    def test_review_digest_does_not_mark_items_not_in_message(self):
        rows = [
            {"source": "linkedin", "job_id": str(i), "title": "A" * 100,
             "company": "B" * 60, "url": "https://example.invalid/" + ("x" * 500)}
            for i in range(10)
        ]
        message, included = review_digest.build_digest(rows)
        self.assertLessEqual(len(message), 3900)
        self.assertGreater(len(included), 0)
        self.assertLess(len(included), len(rows))

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

    def test_bmw_review_is_written_with_title_and_location(self):
        record_id = "https://jobs.bmwgroup.com/job/123"
        reviews = {record_id: {
            "title": "ECU Validation Engineer", "company": "BMW Group",
            "location": "Munich", "url": record_id,
            "score": 45, "posted_at": "",
        }}
        with (
            patch.object(bmw_runner, "job_exists", return_value=False),
            patch.object(bmw_runner, "save_job", return_value=True) as save,
        ):
            inserted, updated, failed = bmw_runner.sync_to_supabase(
                set(), {record_id}, set(), reviews
            )
        self.assertEqual((1, 0, 0), (inserted, updated, failed))
        kwargs = save.call_args.kwargs
        self.assertEqual("review_required@2026-10-06-b", kwargs["status"])
        self.assertEqual("ECU Validation Engineer", kwargs["title"])
        self.assertEqual("Munich", kwargs["location"])

    def test_bmw_sent_metadata_is_saved_for_deduplication(self):
        record_id = "https://jobs.bmwgroup.com/job/456"
        sent_details = {record_id: {
            "title": "ADAS Development Engineer", "company": "BMW Group",
            "location": "Munich", "url": record_id,
            "score": 88, "posted_at": "",
        }}
        with (
            patch.object(bmw_runner, "job_exists", return_value=False),
            patch.object(bmw_runner, "save_job", return_value=True) as save,
        ):
            inserted, updated, failed = bmw_runner.sync_to_supabase(
                set(), {record_id}, {record_id}, {}, sent_details
            )
        self.assertEqual((1, 0, 0), (inserted, updated, failed))
        self.assertEqual("sent", save.call_args.kwargs["status"])
        self.assertEqual("ADAS Development Engineer", save.call_args.kwargs["title"])
        self.assertEqual(88, save.call_args.kwargs["match_score"])

    def test_bmw_review_is_restored_on_matcher_revision(self):
        rows = [
            {"job_id": "old", "status": "review_required@2026-09-30-b"},
            {"job_id": "current", "status": "review_required@2026-10-06-b"},
            {"job_id": "sent", "status": "sent", "sent_to_telegram": True},
        ]
        self.assertEqual({"current", "sent"}, bmw_runner.get_current_seen_ids(rows))

    def test_supabase_update_preserves_review_metadata(self):
        response = MagicMock(status_code=204)
        with patch.object(store, "_check_config"), patch.object(store, "_request", return_value=response) as send:
            store.update_job(
                "bmw", "sample", status="review_required@2026-10-06-b",
                title="Verification Engineer", location="Munich", url="https://example.invalid",
            )
        self.assertEqual("Verification Engineer", send.call_args.kwargs["json"]["title"])
        self.assertEqual("Munich", send.call_args.kwargs["json"]["location"])

    def test_old_review_is_rechecked_when_matcher_changes(self):
        with (
            patch.object(linkedin, "TEST_MODE", False),
            patch.object(linkedin, "get_job_record", return_value={"status": "review_digest_sent@2026-09-30-c", "sent_to_telegram": False}),
        ):
            self.assertFalse(linkedin.already_seen({"job_id": "old", "posted": ""}))

    def test_current_review_does_not_repeat_every_five_minutes(self):
        with (
            patch.object(linkedin, "TEST_MODE", False),
            patch.object(linkedin, "get_job_record", return_value={"status": "review_required@2026-10-06-b", "sent_to_telegram": False}),
        ):
            self.assertTrue(linkedin.already_seen({"job_id": "new", "posted": ""}))


if __name__ == "__main__":
    unittest.main()
