"""Location policy regression tests; no internet, Supabase or Telegram calls."""
import unittest
from unittest.mock import patch

import location_lookup as lookup
from job_matcher import location_status
from linkedin_monitor import location_precheck, final_location_check
from decisions import evaluate_details


class OfflinePlaceTests(unittest.TestCase):
    def test_oberding_passes_both_checks(self):
        location = 'Oberding, Bavaria, Germany'
        self.assertTrue(location_precheck(location)[0])
        self.assertTrue(final_location_check(location, '')[0])

    def test_city_spelling_variants_and_nearby_towns(self):
        for city in ['Munich', 'München', 'Muenchen', 'Munchen', 'Oberding', 'Hallbergmoos',
                     'Erding', 'Freising', 'Dachau', 'Gilching', 'Weßling', 'Wessling',
                     'Augsburg', 'Ingolstadt', 'Regensburg', 'Ulm']:
            with self.subTest(city=city):
                self.assertTrue(location_status(city + ', Germany', '')[0])

    def test_nuremberg_exception_remains(self):
        for city in ['Nuremberg', 'Nürnberg', 'Nuernberg']:
            self.assertTrue(location_status(city + ', Bavaria, Germany', '')[0])

    def test_known_distant_cities_are_rejected(self):
        for city in ['Berlin', 'Hamburg', 'Stuttgart', 'Frankfurt am Main', 'Freiburg im Breisgau']:
            with self.subTest(city=city):
                self.assertIs(location_status(city + ', Germany', '')[0], False)

    def test_unknown_and_ambiguous_names_need_review(self):
        for city in ['Berg', 'Neustadt', 'NotARealPlace', '', 'Germany']:
            with self.subTest(city=city):
                self.assertIsNone(location_status(city, '')[0])
                self.assertTrue(location_precheck(city)[0])

    def test_substrings_do_not_create_false_city_matches(self):
        self.assertIsNone(location_status('Fakeoberdingville, Bavaria, Germany', '')[0])
        self.assertIs(location_status('Berlin, Germany', 'Our customer has an office in Munich.')[0], False)

    def test_postcode_and_multiple_offices(self):
        self.assertTrue(location_status('85445 Oberding, Bavaria, Germany', '')[0])
        self.assertTrue(location_status('Berlin / Munich, Germany', '')[0])

    def test_foreign_country_cannot_be_accepted_as_munich(self):
        self.assertIs(location_status('Munich, Austria', '')[0], False)

    def test_remote_germany_policy(self):
        self.assertTrue(location_status('Berlin, Germany', 'This role is fully remote in Germany.')[0])
        self.assertIs(location_status('Berlin, Germany', 'Hybrid office with homeoffice days.')[0], False)
        self.assertIs(location_status('Berlin, Germany', 'We decided not to become a fully remote company.')[0], False)

    def test_unknown_location_cannot_become_automatic_apply(self):
        breakdown = {'gates_pass': True, 'review_required': False}
        with patch('decisions.evaluate_fit', return_value=(90, [], [], breakdown)):
            decision, evidence, _ = evaluate_details(
                {'title': 'Test Engineer', 'location': 'NotARealPlace'},
                {'description': 'Test CANoe and UDS.', 'requirements': ['CANoe'], 'tasks': ['Test ECUs']})
        self.assertEqual('manual', decision)
        self.assertIn('Location needs review', evidence['reason'])

    def test_lookup_is_cached_and_needs_no_network(self):
        snapshot = lookup.data()
        with patch('requests.get', side_effect=AssertionError('No network allowed')):
            for _ in range(100):
                self.assertTrue(lookup.onsite_location('Oberding, Bavaria, Germany')[0])
        self.assertIs(snapshot, lookup.data())


if __name__ == '__main__':
    unittest.main()
