"""Synthetic engineering-AI cases and formatting regressions, no live services."""
import unittest
from bs4 import BeautifulSoup
from decisions import evaluate_details
import job_matcher as matcher
from linkedin_monitor import extract_sections, SEARCH_QUERY_GROUPS


class OptionalEngineeringAITests(unittest.TestCase):
    def test_optional_ml_is_neither_a_mismatch_nor_core_evidence(self):
        for phrase in ('Machine learning experience is an advantage.',
                       'ML models and machine learning are nice-to-have.',
                       'Ideally you have machine learning experience.',
                       'Kenntnisse in Machine Learning sind wünschenswert.',
                       'Wünschenswerte Kenntnisse in Machine Learning',
                       'Machine Learning ist von Vorteil.',
                       'Machine learning is not required.'):
            item=matcher.evaluate_requirement_phrase(phrase)
            self.assertEqual(item['category'],'optional',phrase)
            self.assertEqual(item['weight'],0,phrase)
            self.assertFalse(item['core'],phrase)

    def test_required_ml_remains_a_real_gap(self):
        for phrase in ('Machine learning is required.',
                       'Machine learning is mandatory, Python is an advantage.',
                       'Machine Learning ist zwingend erforderlich.'):
            item=matcher.evaluate_requirement_phrase(phrase)
            self.assertTrue(item['core'],phrase)
            self.assertLess(item['score'],70,phrase)

    def test_optional_scope_does_not_bleed_across_sentences_or_conjunctions(self):
        phrases=matcher.split_requirement_phrase('Python is required; machine learning and LLMs are an advantage.')
        self.assertEqual(len(phrases),2)
        items=[matcher.evaluate_requirement_phrase(p) for p in phrases]
        self.assertTrue(items[0]['core'])
        self.assertEqual(items[1]['category'],'optional')
        for text in ('Machine learning preferred and Python required',
                     'Machine learning preferred. Python required'):
            items=[matcher.evaluate_requirement_phrase(p) for p in matcher.split_requirement_phrase(text)]
            self.assertEqual(items[0]['category'],'optional')
            self.assertTrue(items[1]['core'])
        phrases=matcher.split_requirement_phrase('Practical scripting experience. Python is a strong advantage.')
        self.assertEqual(len(phrases),2)
        self.assertNotEqual(matcher.evaluate_requirement_phrase(phrases[0])['category'],'optional')

    def test_german_and_english_abbreviations_are_not_sentence_boundaries(self):
        for text in ('Studium (z. B. Mechatronik, Elektrotechnik) oder vergleichbar',
                     'Experience with tools e.g. CANoe',
                     'Modellierungs- bzw. Architektur-Tools'):
            self.assertEqual(matcher.split_requirement_phrase(text),[text])

    def test_paragraph_responsibilities_and_privacy_boundary(self):
        html='''<div><p><strong>Benefits</strong></p><p>Flexible hours</p>
        <p><strong>【Your responsibilities】</strong></p>
        <p><strong>1. Test automation</strong></p>
        <p>Automate diagnostic checks and review test logs.</p>
        <p><strong>【What you bring】</strong></p>
        <ul><li>Experience in vehicle testing.</li><li>Machine learning is an advantage.</li></ul>
        <p><strong>Privacy Statement：</strong></p><ul><li>Data processing and retention details.</li></ul></div>'''
        parsed=extract_sections(BeautifulSoup(html,'html.parser').div)
        self.assertEqual(parsed['tasks'],['Automate diagnostic checks and review test logs.'])
        self.assertEqual(len(parsed['requirements']),2)
        self.assertNotIn('Data processing',' '.join(parsed['requirements']))

    def test_engineering_ai_application_is_reviewed_without_inventing_ml_skills(self):
        requirements=['Degree in vehicle engineering or a related discipline.',
                      'Experience in vehicle testing and engineering development.',
                      'Practical scripting experience. Python is an advantage.',
                      'Ability to assess engineering outputs for technical consistency.',
                      'Machine learning and LLM experience are an advantage.']
        details={'description':' '.join(requirements), 'requirements':requirements,
                 'tasks':['Automate vehicle validation workflows and analyze test measurements.'],
                 'criteria':{'Employment type':'Full-time'}}
        row={'title':'AI Integration Engineer – Vehicle Engineering','location':'Munich'}
        decision,evidence,score=evaluate_details(row,details)
        self.assertEqual(decision,'manual',evidence)
        self.assertEqual(evidence['breakdown']['strong_mismatches'],0)
        self.assertFalse(evidence['breakdown']['gates_pass'])
        details['requirements']=[*requirements[:-1],'Machine learning experience is mandatory.']
        details['description']=' '.join(details['requirements'])
        self.assertEqual(evaluate_details(row,details)[0],'reject')

    def test_optional_fpga_or_pcb_still_hard_rejected(self):
        for keyword in ('FPGA','PCB design'):
            text=f'{keyword} experience is optional.'
            _,_,_,breakdown=matcher.evaluate_fit('Test Engineer',text,[text],[])
            self.assertTrue(breakdown['hard_reject_reason'])
            self.assertFalse(breakdown['review_required'])

    def test_expanded_discovery_preserves_original_search_budget_and_scopes(self):
        self.assertTrue(all(len(group)==6 for group in SEARCH_QUERY_GROUPS))
        queries=[q for group in SEARCH_QUERY_GROUPS for q in group]
        self.assertIn('AI Integration Engineer',queries)
        self.assertIn('Engineering Automation Engineer',queries)
        self.assertIn('ECU Diagnostics Engineer',queries)


if __name__=='__main__':unittest.main()
