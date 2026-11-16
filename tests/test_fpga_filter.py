import unittest
from unittest.mock import patch

from decisions import fit_decision
from description_policy import FPGA_REASON
from job_matcher import evaluate_fit
from notifications import notify_job_once
from scripts import review_digest


class FPGAFilterTests(unittest.TestCase):
    def test_optional_or_compound_mentions_are_hard_rejections(self):
        for text in ("FPGA experience is optional.", "Kenntnisse in FPGAEntwicklung", "FPGAs"):
            with self.subTest(text=text):
                score, _, _, breakdown = evaluate_fit("Test Engineer", text)
                self.assertEqual(("reject", FPGA_REASON), fit_decision("Test Engineer", score, breakdown))
                self.assertFalse(breakdown["review_required"])

    def test_notification_never_reserves_or_sends_manual_review(self):
        job = {"source": "linkedin", "job_id": "sample", "title": "Test Engineer",
               "location": "Munich", "description_text": "Exposure to fpga is a plus"}
        with patch("notifications.claim_notification") as claim, patch("notifications.save_job") as save:
            sender = unittest.mock.Mock()
            self.assertFalse(notify_job_once(job, "MANUAL REVIEW", sender))
            save.assert_not_called()
            claim.assert_not_called()
            sender.assert_not_called()

    def test_stored_description_blocks_when_refetch_fails(self):
        with patch.object(review_digest, "fresh_details", return_value=None):
            decision, evidence, _ = review_digest.review({"source": "linkedin",
                "decision_evidence": {"description": "fpga-based verification"}})
        self.assertEqual(("reject", FPGA_REASON), (decision, evidence["reason"]))
