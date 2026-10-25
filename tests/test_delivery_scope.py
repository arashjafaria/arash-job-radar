"""Reported out-of-scope adverts must never reach a Telegram sender."""
import unittest
from unittest.mock import Mock, patch

from title_policy import excluded_title_reason
from delivery_policy import delivery_block_reason
from job_matcher import location_status
from decisions import evaluate_details, fit_decision
import notifications
from scripts import review_digest


INCIDENTS = [
    {'source': 'linkedin', 'job_id': '4454307152', 'title': 'System Engineer (m/w/d) 2 Jahre befristet',
     'location': 'Geislingen an der Steige, Baden-Württemberg, Germany'},
    {'source': 'linkedin', 'job_id': '4434854463',
     'title': 'Bachelorand im Bereich System Qualification & Application (m/w/d)',
     'location': 'Leonberg, Bavaria, Germany'},
    {'source': 'linkedin', 'job_id': '4473361192', 'title': 'Field Service Engineer 2',
     'location': 'Greater Dresden Area'},
]


class DeliveryScopeTests(unittest.TestCase):
    def test_reported_incidents_are_blocked_even_from_old_manual_queue(self):
        for job in INCIDENTS:
            with self.subTest(job=job['job_id']), \
                 patch.object(notifications, 'save_job') as save, \
                 patch.object(notifications, 'claim_notification') as claim:
                sender = Mock()
                self.assertTrue(delivery_block_reason(job))
                self.assertFalse(notifications.notify_job_once(job, 'MANUAL REVIEW', sender))
                save.assert_not_called()
                claim.assert_not_called()
                sender.assert_not_called()

    def test_it_is_a_title_token_not_part_of_other_words(self):
        for title in ['IT Engineer', 'IT-System Engineer', 'Test Engineer / IT', 'Senior it consultant']:
            self.assertTrue(excluded_title_reason(title), title)
        for title in ['Validation Engineer', 'System Integration Engineer', 'Qualification Test Engineer', 'Circuit Test Engineer']:
            self.assertIsNone(excluded_title_reason(title), title)

    def test_electrical_mechanical_and_german_equivalent_titles_are_excluded(self):
        for title in ['Electrical Engineer (m/f/d)', 'Senior Mechanical Engineer',
                      'Electrical-Engineer', 'Elektroingenieur (m/w/d)', 'Maschinenbauingenieur']:
            self.assertTrue(excluded_title_reason(title), title)
            self.assertEqual('reject', fit_decision(title, 95, {'review_required': True})[0])

    def test_degree_words_in_description_do_not_trigger_title_exclusions(self):
        row = {'title': 'System Test Engineer', 'location': 'Munich'}
        with patch('decisions.evaluate_fit', return_value=(90, [], [], {'gates_pass': True})):
            decision, _, _ = evaluate_details(row, {'description': 'Degree in Electrical Engineering or Mechanical Engineering. Work with IT teams.',
                                                   'requirements': [], 'tasks': []})
        self.assertEqual('apply', decision)

    def test_bachelorand_is_rejected_without_fetching_description(self):
        with patch.object(review_digest, 'fresh_details') as fetch:
            decision, _, _ = review_digest.review(INCIDENTS[1])
        self.assertEqual('reject', decision)
        fetch.assert_not_called()

    def test_metropolitan_labels_resolve_to_city(self):
        for location in ['Greater Dresden Area', 'Greater Dresden Metropolitan Area', 'Metropolregion Dresden', 'Raum Dresden']:
            self.assertIs(location_status(location, '')[0], False, location)
        self.assertTrue(location_status('Greater Munich Area', '')[0])

    def test_unknown_location_is_held_even_when_description_is_unavailable(self):
        job = {'source': 'linkedin', 'job_id': 'unknown', 'title': 'Test Engineer', 'location': 'Unresolved location'}
        with patch.object(review_digest, 'fresh_details', return_value=None):
            decision, evidence, score = review_digest.review(job)
        self.assertEqual('manual', decision)
        with patch.object(review_digest, 'pending_reviews', return_value=[job]), \
             patch.object(review_digest, 'review', return_value=(decision, evidence, score)), \
             patch.object(review_digest, 'record_decision'), \
             patch.object(review_digest, 'update_job') as update, \
             patch.object(review_digest, 'notify_job_once') as notify:
            review_digest.main()
        self.assertTrue(update.call_args.kwargs['status'].startswith('location_review_hold@'))
        notify.assert_not_called()

    def test_onsite_and_hybrid_remote_wording_does_not_bypass_radius(self):
        for text in ['On-site customer support in Dresden, with opportunities to work remotely.',
                     'Work from home two days a week. Three days in our office.']:
            self.assertIs(location_status('Greater Dresden Area, Germany', text)[0], False)

    def test_explicit_fully_remote_germany_still_allowed(self):
        job = {'title': 'Test Engineer', 'location': 'Dresden, Germany',
               'description': 'Fully remote within Germany.'}
        self.assertIsNone(delivery_block_reason(job))

    def test_fresh_verified_location_is_used_in_review_notification(self):
        row = {'source': 'linkedin', 'job_id': 'moved', 'title': 'Test Engineer', 'location': 'Munich'}
        evidence = {'title': 'Test Engineer', 'location': 'Greater Dresden Area', 'description': 'On-site in Dresden',
                    'decision': 'manual', 'reason': 'uncertain requirements'}
        with patch.object(review_digest, 'pending_reviews', return_value=[row]), \
             patch.object(review_digest, 'review', return_value=('manual', evidence, 50)), \
             patch.object(review_digest, 'record_decision'), patch.object(review_digest, 'update_job'), \
             patch.object(review_digest, 'notify_job_once') as notify:
            review_digest.main()
        notify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
