"""Lifetime delivery protection and review decisions, without live services."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import notifications as notify
import supabase_store as store
import linkedin_monitor as linkedin
import bmw_monitor as bmw
from scripts import review_digest
from decisions import evaluate_details


JOB = {"source": "linkedin", "job_id": "4475374427", "title": "Test Engineer",
       "company": "Example", "location": "Munich", "url": "https://example.invalid/4475374427"}


class TestNotificationProtection(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(notify, "save_job"), patch.object(notify, "update_job"),
                        patch.object(notify, "finish_notification")]
        self.save, self.update, self.finish = [p.start() for p in self.patches]
        for p in self.patches:
            self.addCleanup(p.stop)

    def test_prior_delivery_or_digest_suppresses_sender(self):
        sender = Mock()
        with patch.object(notify, "claim_notification", return_value=False):
            self.assertFalse(notify.notify_job_once(JOB, "APPLY", sender))
        sender.assert_not_called()
        self.finish.assert_not_called()

    def test_single_claim_one_message_even_for_long_description(self):
        sender = Mock(return_value=True)
        events = []
        with patch.object(notify, "claim_notification", side_effect=lambda *a: events.append("claimed") or True):
            sender.side_effect = lambda *a: events.append("sent") or True
            self.assertTrue(notify.notify_job_once(JOB, "X" * 10000, sender))
        self.assertEqual(["claimed", "sent"], events)
        sender.assert_called_once()
        self.assertLessEqual(len(sender.call_args.args[0]), 3900)
        self.assertIn(JOB["url"], sender.call_args.args[0])
        self.assertTrue(self.finish.call_args.args[-1])

    def test_timeout_is_uncertain_and_never_retried(self):
        sender = Mock(side_effect=requests.Timeout("reply lost"))
        with patch.object(notify, "claim_notification", side_effect=[True, False]):
            with self.assertRaises(requests.Timeout):
                notify.notify_job_once(JOB, "APPLY", sender)
            self.assertFalse(notify.notify_job_once(JOB, "APPLY", sender))
        sender.assert_called_once()
        self.assertFalse(self.finish.call_args.args[-1])

    def test_telegram_success_db_finish_failure_does_not_resend(self):
        sender = Mock(return_value=True)
        self.finish.side_effect = RuntimeError("DB outcome failed")
        with patch.object(notify, "claim_notification", side_effect=[True, False]):
            with self.assertRaises(RuntimeError):
                notify.notify_job_once(JOB, "APPLY", sender)
            self.assertFalse(notify.notify_job_once(JOB, "APPLY", sender))
        sender.assert_called_once()

    def test_database_claim_failure_never_contacts_telegram(self):
        sender = Mock()
        with patch.object(notify, "claim_notification", side_effect=RuntimeError("DB down")):
            with self.assertRaises(RuntimeError):
                notify.notify_job_once(JOB, "APPLY", sender)
        sender.assert_not_called()

    def test_false_delivery_flag_is_not_written_by_re_evaluation(self):
        response = Mock(status_code=204)
        with patch.object(store, "_check_config"), patch.object(store, "_request", return_value=response) as request:
            store.update_job("linkedin", JOB["job_id"], status="rejected_requirements", sent_to_telegram=False)
        self.assertNotIn("sent_to_telegram", request.call_args.kwargs["json"])

    def test_rpc_migration_missing_fails_closed(self):
        with patch.object(store, "_check_config"), patch.object(store, "_request", return_value=Mock(status_code=404)):
            with self.assertRaises(RuntimeError):
                store.claim_notification("linkedin", JOB["job_id"], "test-token")

    def test_sent_repost_can_be_evaluated_again(self):
        with patch.object(linkedin, "TEST_MODE", False), patch.object(linkedin, "get_job_record", return_value={
            "sent_to_telegram": True, "status": "sent", "posted_at": "2026-10-01"}):
            self.assertFalse(linkedin.already_seen({**JOB, "posted": "2026-10-09"}))
        # The separate permanent reservation test above ensures no resend.

    def test_same_instant_different_timestamp_format_is_not_a_repost(self):
        self.assertFalse(linkedin.posting_changed("2026-10-09T00:00:00Z", "2026-10-09T00:00:00+00:00"))
        self.assertFalse(linkedin.posting_changed("2026-10-09", "2026-10-09T00:00:00+00:00"))

    def test_missing_timestamp_baseline_can_be_initialized_without_resending(self):
        self.assertTrue(linkedin.posting_changed("2026-10-09", ""))
        self.assertFalse(linkedin.posting_changed("", "2026-10-09"))


class TestSecondReview(unittest.TestCase):
    def test_bmw_main_keeps_match_flow_and_uses_guarded_delivery(self):
        job = {"title": "Test Engineer", "url": "https://jobs.example.invalid/123"}
        details = {"location": "Munich", "date_posted": "", "employment_type": "FULL_TIME",
                   "description_text": "CAN diagnostics validation", "requirements": ["CAN diagnostics"],
                   "tasks": [], "benefits": [], "other": []}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(bmw, "get_bmw_jobs", return_value=[job]), \
             patch.object(bmw, "load_seen_jobs", return_value=set()), \
             patch.object(bmw, "save_seen_jobs"), \
             patch.object(bmw, "get_job_details", return_value=details), \
             patch.object(bmw, "cv_location_status", return_value=(True, "Munich")), \
             patch.object(bmw, "cv_evaluate_fit", return_value=(90, ["CAN"], [], {"gates_pass": True})), \
             patch.object(bmw, "find_sent_duplicate", return_value=None), \
             patch.object(bmw, "save_job"), patch.object(bmw, "record_decision") as evidence, \
             patch.object(bmw, "notify_job_once", return_value=True) as notification, \
             patch.object(bmw, "send_telegram") as direct, \
             patch.object(bmw, "SENT_FILE", str(Path(directory) / "sent.json")), \
             patch.object(bmw, "SENT_DETAILS_FILE", str(Path(directory) / "details.json")), \
             patch.object(bmw, "REVIEW_FILE", str(Path(directory) / "reviews.json")):
            bmw.main()
        evidence.assert_called_once()
        notification.assert_called_once()
        self.assertEqual("bmw", notification.call_args.args[0]["source"])
        self.assertEqual(job["url"], notification.call_args.args[0]["job_id"])
        direct.assert_not_called()

    def test_4475374427_review_becomes_explicit_apply_without_reposting(self):
        # Behavioral fixture only: real job requirements were not supplied.
        rows = [{**JOB, "status": "review_digest_sent@old", "sent_to_telegram": False}]
        with patch.object(review_digest, "pending_reviews", return_value=rows), \
             patch.object(review_digest, "review", return_value=("apply", {"decision": "apply", "reason": "verified gates passed"}, 90)), \
             patch.object(review_digest, "record_decision") as record, \
             patch.object(review_digest, "update_job"), \
             patch.object(review_digest, "notify_job_once", return_value=False) as notification:
            review_digest.main()
        self.assertEqual("apply", record.call_args.args[2])
        notification.assert_called_once()

    def test_reject_is_stored_without_any_notification_attempt(self):
        with patch.object(review_digest, "pending_reviews", return_value=[JOB]), \
             patch.object(review_digest, "review", return_value=("reject", {"decision": "reject", "reason": "unsupported core"}, 20)), \
             patch.object(review_digest, "record_decision") as record, \
             patch.object(review_digest, "update_job"), \
             patch.object(review_digest, "notify_job_once") as notification:
            review_digest.main()
        self.assertEqual("reject", record.call_args.args[2])
        notification.assert_not_called()

    def test_missing_description_is_manual_with_a_specific_reason(self):
        with patch.object(review_digest, "fresh_details", return_value=None):
            decision, evidence, score = review_digest.review(JOB)
        self.assertEqual("manual", decision)
        self.assertIn("unavailable", evidence["reason"])
        self.assertIsNone(score)

    def test_4449780097_uses_geographic_list_instead_of_missing_name_rejection(self):
        row = {**JOB, "job_id": "4449780097", "location": "Lindenberg im Allgäu"}
        decision, evidence, score = evaluate_details(row, {"description": "Engineering test role", "requirements": []})
        self.assertEqual("manual", decision)
        self.assertIn("location", evidence["checks"])
        self.assertIsNotNone(score)

    def test_paragraph_requirements_receive_independent_second_extraction(self):
        details = {"description": "Qualifications", "requirements": [], "tasks": [],
                   "description_html": "<h3>Qualifications</h3><p>Experience with CAN diagnostics and ECU validation.</p>"}
        with patch.object(linkedin, "get_job_details", return_value=details):
            result = review_digest.fresh_details(JOB)
        self.assertIn("CAN", " ".join(result["requirements"]))

    def test_unknown_proprietary_requirements_stay_manual_not_invented_apply(self):
        decision, evidence, _ = evaluate_details(JOB, {
            "description": "Internal proprietary validation protocol.",
            "requirements": ["Knowledge of internal proprietary validation protocol."],
            "tasks": ["Support validation teams."],
        })
        self.assertEqual("manual", decision)
        self.assertIn("no verified core evidence", evidence["reason"])
        self.assertIn("requirement_details", evidence["breakdown"])


if __name__ == "__main__":
    unittest.main()
