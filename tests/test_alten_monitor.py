"""ALTEN parser, duplicate and dry-run safety regressions; no live calls."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import alten_monitor as alten

URL = alten.BASE + '/en/jobs/744000123456789-test-engineer-all-gender/'
LISTING = '''<h3 class="wp-block-jobboard-filter__counts"><span class="has-secondary-color">1</span></h3>
<div class="offer-list-item"><a class="card-title" href="''' + URL + '''">Test Engineer (all gender)</a>
<div class="card-location"><span class="location-list">Munich (1 km)</span></div>
<div class="card-date">21/10/2026</div></div>'''
DETAIL = '''<h2 class="is-style-page-title wp-block-post-title">Test Engineer (all gender)</h2>
<div class="wp-block-jobboard-offer-meta"><h4 class="offer-outro-title">Benefits</h4><ul><li>Free coffee</li></ul></div>
<div class="wp-block-jobboard-offer-meta"><h4 class="offer-tasks-title">Make it happen</h4><ul><li>Perform ECU integration tests.</li></ul></div>
<div class="wp-block-jobboard-offer-meta"><h4 class="offer-requirements-title">Be our forward thinker</h4><ul><li>Experience in CANoe and UDS diagnostics.</li></ul></div>
<span title="Reference">REF123L</span><span title="Location">Munich</span><span title="Publication date">21/10/2026</span>'''


class AltenPilotTests(unittest.TestCase):
    def candidate(self):
        return alten.parse_listing(LISTING)[0][0]

    def test_search_has_coordinates_radius_and_newest_sort(self):
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(alten.search_url(2)).query)
        self.assertEqual(['25'], params['distance'])
        self.assertEqual(['48.1351253'], params['location[lat]'])
        self.assertEqual(['2'], params['pagenum'])
        self.assertEqual(['date'], params['sortby'])

    def test_cards_and_detail_sections_do_not_include_benefits_as_requirements(self):
        candidate = self.candidate()
        self.assertEqual('2026-10-21', candidate['posted_at'])
        detail = alten.parse_detail(DETAIL, candidate)
        self.assertEqual(['Experience in CANoe and UDS diagnostics.'], detail['requirements'])
        self.assertEqual('REF123L', detail['requisition_id'])

    def test_markup_failures_are_not_successful_empty_searches(self):
        with self.assertRaises(ValueError):
            alten.parse_listing('<html>Access denied</html>')
        with self.assertRaises(ValueError):
            alten.parse_detail('<html>No longer available</html>', self.candidate())

    def test_tracking_and_language_variant_share_website_identity(self):
        row = {**self.candidate(), 'job_id': 'mirror', 'url': URL.replace('/en/jobs/', '/jobs/') + '?trk=123'}
        self.assertEqual('duplicate', alten.duplicate_check(self.candidate(), [row])['state'])

    def test_reference_matches_pending_linkedin_record(self):
        detail = alten.parse_detail(DETAIL, self.candidate())
        row = {'company': 'ALTEN Germany', 'source': 'linkedin', 'job_id': '123',
               'description': 'Reference: REF123L', 'status': 'review_required'}
        self.assertEqual('same_requisition', alten.duplicate_check(detail, [row])['reason'])

    def test_same_title_is_held_but_distinct_cities_not_merged(self):
        job = self.candidate()
        row = {**job, 'source': 'linkedin', 'url': 'https://linkedin.com/jobs/view/123',
               'title': 'Test Engineer (all gender) gg', 'location': 'Munich, Bavaria, Germany'}
        self.assertEqual('possible_duplicate', alten.duplicate_check(job, [row])['state'])
        row['location'] = 'Berlin, Germany'
        self.assertEqual('no_match_found', alten.duplicate_check(job, [row])['state'])

    def test_exact_24_hour_age_gate_and_unknown_dates(self):
        job = {**self.candidate(), 'posted_at': '2026-10-19'}
        now = datetime(2026, 10, 21, 10, tzinfo=timezone.utc)
        self.assertEqual('older_than_age_limit', alten.assess(job, now=now)['reason'])
        job['posted_at'] = ''
        self.assertEqual('manual', alten.assess(job, now=now)['decision'])

    def test_sales_roles_do_not_spend_detail_budget(self):
        job = {**self.candidate(), 'title': 'Business Manager / Account Manager'}
        self.assertEqual('sales_or_administrative_role', alten.assess(
            job, now=datetime(2026, 10, 21, 10, tzinfo=timezone.utc))['reason'])

    def test_repeat_pagination_fails_instead_of_silently_missing_jobs(self):
        session = Mock()
        session.get.return_value.text = LISTING.replace('>1</span>', '>2</span>')
        with self.assertRaises(RuntimeError):
            alten.run(session, [], pause=0)

    def test_pilot_performs_get_only_and_returns_no_send_or_write(self):
        session = Mock()
        session.get.side_effect = [Mock(text=LISTING), Mock(text=DETAIL)]
        report = alten.run(session, [], max_age_hours=1e6, pause=0)
        self.assertEqual([], report['summary']['detail_errors'])
        self.assertEqual(0, report['summary']['telegram_messages_sent'])
        self.assertEqual(0, report['summary']['database_writes'])
        session.post.assert_not_called()
        session.patch.assert_not_called()

    def test_history_column_aliases_and_fail_closed_read(self):
        session = Mock()
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = []
        with patch.object(alten, 'SUPABASE_URL', 'https://test.invalid'), patch.object(alten, 'SUPABASE_SECRET_KEY', 'test-only'):
            self.assertEqual([], alten.load_existing(session))
            history_params = session.get.call_args.kwargs['params']
            self.assertIn('title:title_key', history_params['select'])
            self.assertIn('company_key', history_params)
            session.get.return_value.status_code = 503
            with self.assertRaises(RuntimeError):
                alten.load_existing(session)

    def report(self, decision='apply'):
        job = alten.parse_detail(DETAIL, self.candidate())
        job['assessment'] = {'decision': decision, 'reason': 'verified', 'score': 80}
        return {'summary': {'listing_complete': True, 'database_writes': 0}, 'jobs': [job]}

    def test_publication_rechecks_live_duplicates_and_does_not_store_them(self):
        report = self.report()
        row = {**report['jobs'][0], 'source': 'linkedin', 'job_id': 'li', 'url': 'https://linkedin.com/123'}
        with patch.object(alten, 'assess', return_value=report['jobs'][0]['assessment']), \
             patch.object(alten, 'load_existing', return_value=[row]), \
             patch.object(alten, 'save_job') as save, patch.object(alten, 'notify_job_once') as notify:
            self.assertEqual(0, alten.publish(report, Mock()))
            save.assert_not_called()
            notify.assert_not_called()

    def test_eligible_job_uses_shared_notification_reservation(self):
        report = self.report()
        with patch.object(alten, 'assess', return_value=report['jobs'][0]['assessment']), \
             patch.object(alten, 'load_existing', return_value=[]), \
             patch.object(alten, 'save_job'), patch.object(alten, 'record_decision'), \
             patch.object(alten, 'notify_job_once', return_value=True) as notify:
            self.assertEqual(1, alten.publish(report, Mock()))
            notify.assert_called_once()

    def test_old_job_cannot_be_published_after_scan(self):
        report = self.report()
        with patch.object(alten, 'assess', return_value={'decision': 'reject', 'reason': 'older_than_age_limit'}), \
             patch.object(alten, 'notify_job_once') as notify:
            self.assertEqual(0, alten.publish(report, Mock()))
            notify.assert_not_called()

    def test_manual_job_is_queued_without_immediate_telegram(self):
        report = self.report('manual')
        with patch.object(alten, 'assess', return_value=report['jobs'][0]['assessment']), \
             patch.object(alten, 'load_existing', return_value=[]), \
             patch.object(alten, 'save_job') as save, patch.object(alten, 'record_decision'), \
             patch.object(alten, 'notify_job_once') as notify:
            self.assertEqual(0, alten.publish(report, Mock()))
            self.assertTrue(save.call_args.kwargs['status'].startswith('review_required@'))
            notify.assert_not_called()

    def test_linkedin_send_is_blocked_by_alten_uncertain_history(self):
        import notifications
        job = {**self.candidate(), 'source': 'linkedin', 'job_id': 'li'}
        history = {**self.candidate(), 'notification_status': 'uncertain'}
        with patch.object(alten, 'load_existing', return_value=[history]), \
             patch.object(notifications, 'claim_notification') as claim:
            sender = Mock()
            self.assertFalse(notifications.notify_job_once(job, 'test', sender))
            sender.assert_not_called()
            claim.assert_not_called()

    def test_alten_second_review_rejects_stale_description(self):
        from scripts import review_digest
        job = {**self.candidate(), 'posted_at': '2020-01-01'}
        detail = alten.parse_detail(DETAIL, job)
        detail['posted_at'] = '2020-01-01'
        with patch.object(review_digest, 'fresh_details', return_value=detail):
            decision, evidence, _ = review_digest.review(job)
        self.assertEqual('reject', decision)
        self.assertEqual('older_than_age_limit', evidence['reason'])


if __name__ == '__main__':
    unittest.main()
