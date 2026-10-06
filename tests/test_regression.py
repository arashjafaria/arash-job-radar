"""Offline regression baseline. No website, Supabase, or Telegram access."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import job_matcher as matcher
import market_monitor as market
import supabase_store as store


FIXTURES = Path(__file__).parent / "fixtures" / "matching_cases.json"


class TestMatchingCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]

    def test_fixture_has_45_labeled_scenarios(self):
        self.assertEqual(45, len(self.cases))
        self.assertEqual({"accept", "reject", "review"}, {case["expected"] for case in self.cases})

    def test_45_scenarios(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                _, _, _, decision = matcher.evaluate_fit(
                    case["title"],
                    " ".join(case["requirements"] + case["tasks"]),
                    case["requirements"],
                    case["tasks"],
                )
                predicted = (
                    "accept" if decision["gates_pass"]
                    else "review" if decision["review_required"]
                    else "reject"
                )
                self.assertEqual(case["expected"], predicted, decision)

    def test_observed_real_postings_do_not_autopass(self):
        real_file = Path(__file__).parent / "fixtures" / "real_observed_cases.json"
        cases = json.loads(real_file.read_text(encoding="utf-8"))["cases"]
        for case in cases:
            with self.subTest(real=case["id"]):
                _, _, _, decision = matcher.evaluate_fit(
                    case["title"],
                    " ".join(case["requirements"] + case["tasks"]),
                    case["requirements"],
                    case["tasks"],
                )
                self.assertFalse(decision["gates_pass"], decision)
                self.assertTrue(decision["review_required"], decision)

    def test_absent_core_requirements_cannot_score_perfect(self):
        _, _, _, decision = matcher.evaluate_fit(
            "System Engineer",
            "Good communication and excellent motivation.",
            ["Good communication and excellent motivation."],
            ["Support the engineering team."],
        )
        self.assertFalse(decision["gates_pass"])
        self.assertFalse(decision["core_evidence"])
        self.assertEqual(0, decision["core_requirements"])
        self.assertTrue(decision["review_required"])

    def test_unknown_not_silently_rejected(self):
        _, _, _, decision = matcher.evaluate_fit(
            "Test Engineer", "An internal proprietary validation protocol.",
            ["Knowledge of internal proprietary validation protocol."],
            ["Support validation teams."],
        )
        self.assertFalse(decision["gates_pass"])
        self.assertTrue(decision["review_required"])

    def test_known_unsupported_core_is_not_review(self):
        _, _, _, decision = matcher.evaluate_fit(
            "System Engineer", "Kubernetes and Terraform.",
            ["Strong professional experience with Kubernetes and Terraform."],
            ["Maintain cloud infrastructure and DNS."],
        )
        self.assertFalse(decision["gates_pass"])
        self.assertFalse(decision["review_required"])


class TestPolicyInvariants(unittest.TestCase):
    def test_native_german_rejected(self):
        reject, detail, _ = matcher.german_requirement("Native German required")
        self.assertTrue(reject)
        self.assertIn("Native", detail)

    def test_c1_c2_warned_not_silently_rejected(self):
        for phrase in ("German C1 required", "Deutsch C2 erforderlich", "fluent German required"):
            with self.subTest(phrase=phrase):
                reject, detail, _ = matcher.german_requirement(phrase)
                self.assertFalse(reject)
                self.assertIn("⚠️", detail)

    def test_b2_warning(self):
        reject, detail, _ = matcher.german_requirement("German B2 preferred")
        self.assertFalse(reject)
        self.assertIn("B2", detail)

    def test_known_degree_and_tools(self):
        score, matched, _, decision = matcher.evaluate_fit(
            "ECU Test Engineer",
            "Experience with UDS and ecu.test; perform regression testing",
            ["Experience with UDS and ecu.test"],
            ["Execute ECU regression testing and defect analysis"],
        )
        self.assertGreaterEqual(score, 60)
        self.assertTrue(decision["gates_pass"])
        self.assertTrue(decision["core_evidence"])

    def test_contract_hard_requirement(self):
        rejected, _ = matcher.contract_status(
            {"employment type": "PART_TIME"}, "Part-time contract"
        )
        self.assertTrue(rejected)

    def test_location_munich(self):
        valid, _ = matcher.location_status("Munich, Germany", "")
        self.assertTrue(valid)

    def test_unknown_outside_region_not_accepted(self):
        valid, _ = matcher.location_status("Berlin, Germany", "Hybrid office Berlin")
        self.assertFalse(valid)

    def test_remote_germany(self):
        valid, _ = matcher.location_status(
            "Berlin, Germany", "Fully remote within Germany"
        )
        self.assertTrue(valid)


class TestDataPipeline(unittest.TestCase):
    def test_structured_jobposting_discovery(self):
        posting = {"@context": "https://schema.org", "@graph": [{"@type": "JobPosting", "title": "ECU Tester"}]}
        self.assertEqual("ECU Tester", market.find_job_posting(posting)["title"])

    def test_html_section_parser(self):
        sections = market.extract_sections(
            "<h2>Responsibilities</h2><ul><li>Validate ECU system functions</li></ul>"
            "<h2>Requirements</h2><ul><li>Experience with UDS diagnostics</li></ul>"
        )
        self.assertIn("Validate ECU system functions", sections["tasks"])
        self.assertIn("Experience with UDS diagnostics", sections["requirements"])

    def test_dry_run_never_sends_or_persists(self):
        candidate = {"source": "stepstone", "job_id": "1234", "url": "https://example.invalid", "title": "Test"}
        with patch.object(market, "DRY_RUN", True), patch.object(market.requests, "post") as post, patch.object(market, "save_job") as save:
            self.assertTrue(market.send_telegram("offline dry run"))
            market.remember(candidate, None, "review_required")
            post.assert_not_called()
            save.assert_not_called()

    def test_dry_run_single_search_area(self):
        with patch.object(market, "DRY_RUN", True):
            urls = market.stepstone_urls("System Test Engineer")
            self.assertEqual(1, len(urls))
            self.assertEqual("Munich", urls[0][0])

    def test_repository_duplicate_lookup_normalizes_title(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [{
            "source": "linkedin", "job_id": "x",
            "title": "Entwicklungsingenieur (m/w/d)",
            "company": "Example GmbH", "location": "München",
        }]
        with patch.object(store, "_check_config"), patch.object(store, "_request", return_value=response):
            duplicate = store.find_sent_duplicate(
                "stepstone", "Development Engineer", "Example", "Munich"
            )
        self.assertIsNotNone(duplicate)

    def test_duplicate_lookup_does_not_match_unrelated_company(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [{
            "source": "linkedin", "job_id": "x", "title": "Development Engineer",
            "company": "Other Company", "location": "Munich",
        }]
        with patch.object(store, "_check_config"), patch.object(store, "_request", return_value=response):
            self.assertIsNone(
                store.find_sent_duplicate(
                    "stepstone", "Development Engineer", "Example GmbH", "Munich"
                )
            )


if __name__ == "__main__":
    unittest.main()
