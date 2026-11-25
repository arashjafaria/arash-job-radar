import unittest
from unittest.mock import patch
from remote_policy import offers_remote_work
from job_matcher import location_status
from linkedin_monitor import location_precheck
from delivery_policy import delivery_block_reason
from decisions import evaluate_details

class RemotePolicyTests(unittest.TestCase):
    def test_remote_and_mobile_spelling_variants_override_any_city(self):
        for offer in ('Fully remote', '100% Remote', '100 % Homeoffice', 'vollständig remote', 'komplett im Homeoffice', 'Remote 100%'):
            for city in ('Germany', 'Berlin', 'Greater Dresden Area', 'Unknown city', ''):
                with self.subTest(offer=offer, city=city):
                    self.assertTrue(location_status(city, offer)[0])

    def test_title_remote_is_honored_by_final_delivery_guard(self):
        self.assertIsNone(delivery_block_reason({'title':'Validation Engineer — Fully Remote', 'location':'Germany', 'description':'UDS testing'}))
        self.assertIsNone(delivery_block_reason({'title':'Validation Engineer', 'location':'Dresden', 'description':'100% Remote möglich.'}))

    def test_remote_does_not_disable_other_hard_filters(self):
        for job in ({'title':'Full-Stack Engineer Remote','description':'remote'},
                    {'title':'Test Engineer Remote','description':'FPGA required'},
                    {'title':'Test Engineer Remote','description':'PCB design'}):
            self.assertTrue(delivery_block_reason({**job,'location':'Germany'}))
        with patch('decisions.evaluate_fit') as fit:
            decision, evidence, _ = evaluate_details({'title':'Test Engineer','location':'Germany'},
                {'description':'Remote work. Verhandlungssichere Deutschkenntnisse auf C1-Niveau.'})
        self.assertEqual('reject',decision)
        self.assertIn('German',evidence['reason'])
        fit.assert_not_called()

    def test_absent_or_negated_remote_does_not_bypass_geography(self):
        for text in ('Onsite in Dresden.', 'Hybrid office in Dresden.', 'No remote work.', 'Kein Homeoffice.', 'Mobiles Arbeiten ist nicht möglich.', 'Remote control of vehicle systems.', 'Remote sensing algorithms.'):
            self.assertFalse(offers_remote_work(text),text)
            self.assertFalse(location_status('Dresden',text)[0],text)

    def test_outside_card_reaches_description_before_location_rejection(self):
        self.assertTrue(location_precheck('Dresden')[0])
        self.assertFalse(location_status('Dresden','Full time onsite in Dresden.')[0])

    def test_alten_remote_title_is_not_discarded_by_feed_radius(self):
        from alten_monitor import feed_candidate
        item = {'id':'1234', 'name':'Test Engineer Fully Remote', 'location':{'country':'de','city':'Berlin','latitude':52.52,'longitude':13.405}}
        self.assertIsNotNone(feed_candidate(item))
        item['location']['latitude'] = 'NaN'
        self.assertIsNotNone(feed_candidate(item))
        item['name'] = 'Test Engineer Onsite'
        self.assertIsNone(feed_candidate(item))

    def test_partial_remote_is_only_accepted_within_existing_area(self):
        for wording in ('Mobiles Arbeiten nach Absprache', 'Remote', 'Hybrid', 'Homeoffice möglich', 'Work remotely two days per week'):
            self.assertTrue(location_status('Munich', wording)[0])
            self.assertFalse(location_status('Rüsselsheim, Germany', wording)[0])
            self.assertIsNot(location_status('Germany', wording)[0], True)

    def test_required_office_attendance_prevents_full_remote_override(self):
        for wording in ('Fully remote. Mandatory onsite attendance every week.', '100% remote. Two days per week in our office.', 'Fully remote. Regelmäßige Präsenz im Büro erforderlich.'):
            self.assertFalse(location_status('Rüsselsheim, Germany', wording)[0])
        self.assertFalse(location_status('Berlin', 'Not fully remote')[0])

    def test_optional_mobile_work_does_not_waive_city_policy(self):
        self.assertIsNot(location_status('Germany', 'Option auf mobiles Arbeiten nach Absprache.')[0], True)
