import unittest
from unittest.mock import patch
from remote_policy import offers_remote_work
from job_matcher import location_status
from linkedin_monitor import location_precheck
from delivery_policy import delivery_block_reason
from decisions import evaluate_details

class RemotePolicyTests(unittest.TestCase):
    def test_remote_and_mobile_spelling_variants_override_any_city(self):
        for offer in ('Remote', 'Work remotely', 'mobiles Arbeiten', 'mobile Arbeit', 'Mobilarbeit', 'Mobiles-Arbeiten', 'Homeoffice', 'Home Office', 'working from home'):
            for city in ('Germany', 'Berlin', 'Greater Dresden Area', 'Unknown city', ''):
                with self.subTest(offer=offer, city=city):
                    self.assertTrue(location_status(city, offer)[0])

    def test_title_remote_is_honored_by_final_delivery_guard(self):
        self.assertIsNone(delivery_block_reason({'title':'Validation Engineer — Remote', 'location':'Germany', 'description':'UDS testing'}))
        self.assertIsNone(delivery_block_reason({'title':'Validation Engineer', 'location':'Dresden', 'description':'Möglichkeit für mobiles Arbeiten.'}))

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
        item = {'id':'1234', 'name':'Test Engineer Remote', 'location':{'country':'de','city':'Berlin','latitude':52.52,'longitude':13.405}}
        self.assertIsNotNone(feed_candidate(item))
        item['location']['latitude'] = 'NaN'
        self.assertIsNotNone(feed_candidate(item))
        item['name'] = 'Test Engineer Onsite'
        self.assertIsNone(feed_candidate(item))

    def test_optional_mobile_work_is_enough_under_user_policy(self):
        self.assertTrue(location_status('Germany', 'Option auf mobiles Arbeiten nach Absprache.')[0])
