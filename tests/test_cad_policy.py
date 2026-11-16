import unittest

from cad_policy import cad_block_reason
from decisions import fit_decision
from delivery_policy import delivery_block_reason
from job_matcher import evaluate_fit


class CadPolicyTests(unittest.TestCase):
    def test_required_design_bypasses_manual_review(self):
        for requirement in (
            "Fundierte Erfahrung in der 3D-Konstruktion mit CATIA",
            "Proven experience creating 3D models using Siemens NX or Creo",
            "Erfahrung in der 3D-Konstruktion, idealerweise mit CATIA",
        ):
            with self.subTest(requirement=requirement):
                score, _, _, breakdown = evaluate_fit("Test Engineer", "", [requirement])
                self.assertFalse(breakdown["review_required"])
                self.assertEqual("reject", fit_decision("Test Engineer", score, breakdown)[0])
                self.assertTrue(delivery_block_reason({
                    "title": "Test Engineer", "location": "Munich",
                    "decision_evidence": {"requirements": [requirement]},
                }))

    def test_optional_or_non_design_is_not_blocked(self):
        for requirement in (
            "SolidWorks-Kenntnisse sind von Vorteil",
            "Experience with CAD design is an advantage",
            "Ability to read CAD drawings for test planning",
            "Kenntnisse in CATIA",
        ):
            with self.subTest(requirement=requirement):
                self.assertIsNone(cad_block_reason([requirement], requirement))
