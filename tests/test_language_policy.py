"""Mandatory advanced German is excluded; optional German and English are scoped."""
import unittest
from unittest.mock import patch

from job_matcher import german_requirement
from decisions import evaluate_details
from scripts import review_digest


class TestGermanPolicy(unittest.TestCase):
    def test_required_advanced_german_is_a_hard_filter(self):
        for text in ("German C1 required", "Deutsch C2 erforderlich", "C1 German",
                     "Fluent German", "fluent in German", "German must be fluent",
                     "Fließende Deutschkenntnisse", "Verhandlungssichere Deutschkenntnisse",
                     "Deutsch in Wort und Schrift verhandlungssicher",
                     "Fluent English and German required", "German and English C1",
                     "Native German required", "Deutsch als Muttersprache",
                     "Deutschkenntnisse mindestens C1", "Deutsch (mind. C1)",
                     "German proficiency at least C1", "Fluency in German"):
            with self.subTest(text=text):
                self.assertTrue(german_requirement(text)[0], german_requirement(text))

    def test_optional_advanced_german_does_not_reject(self):
        for text in ("German C1 preferred", "Fluent German is a plus",
                     "German C2 optional", "Verhandlungssicheres Deutsch wünschenswert",
                     "Native German is not required", "German C1 not mandatory",
                     "Ideally fluent German", "English or German fluent",
                     "German B2/C1", "German C1 or B2"):
            with self.subTest(text=text):
                self.assertFalse(german_requirement(text)[0], german_requirement(text))

    def test_english_levels_never_become_german_levels(self):
        for text in ("Fluent English; German is a plus", "Fluent English, German preferred",
                     "English C1 and German B1", "Native English; German B1",
                     "German B1, English C2", "English fluent and German basic",
                     "Fluent English", "English C1 required"):
            with self.subTest(text=text):
                rejected, reason, _ = german_requirement(text)
                self.assertFalse(rejected)
                self.assertNotIn("German C1/C2/fluent", reason)

    def test_explicit_mandatory_clause_overrides_separate_preference(self):
        self.assertTrue(german_requirement("German optional for some teams; German C1 required for this role")[0])

    def test_second_review_cannot_override_mandatory_german(self):
        row = {"source": "linkedin", "job_id": "synthetic", "title": "ECU Test Engineer",
               "company": "Example", "location": "Munich", "url": "https://example.invalid"}
        details = {"description": "ECU validation. German C1 required.",
                   "requirements": ["German C1 required"], "tasks": ["Test ECU diagnostics"]}
        with patch("decisions.evaluate_fit") as score:
            decision, evidence, _ = evaluate_details(row, details)
        self.assertEqual("reject", decision)
        self.assertIn("German C1/C2/fluent required", evidence["reason"])
        score.assert_not_called()
        with patch.object(review_digest, "pending_reviews", return_value=[row]), \
             patch.object(review_digest, "review", return_value=(decision, evidence, None)), \
             patch.object(review_digest, "record_decision"), \
             patch.object(review_digest, "update_job"), \
             patch.object(review_digest, "notify_job_once") as notify:
            review_digest.main()
        notify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
