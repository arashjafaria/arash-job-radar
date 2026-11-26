import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
from bs4 import BeautifulSoup
import job_boards_monitor as boards

NOW = datetime(2026, 11, 26, 16, tzinfo=timezone.utc)


def details_html(**overrides):
    data = {'@type': 'JobPosting', 'title': 'System Test Engineer',
            'datePosted': (NOW - timedelta(hours=2)).isoformat(),
            'hiringOrganization': {'name': 'Example GmbH'},
            'jobLocation': {'address': {'addressLocality': 'Munich', 'addressCountry': 'DE'}},
            'employmentType': 'FULL_TIME',
            'description': 'Aufgaben <ul><li>Test and validate vehicle control units with CANoe and automated test equipment.</li></ul> Profil <ul><li>Experience in vehicle validation with CANoe and Python.</li></ul> Benefits <ul><li>Flexible working hours.</li></ul>'}
    data.update(overrides)
    return BeautifulSoup('<script type="application/ld+json">'+json.dumps(data)+'</script>', 'html.parser')


class BoardTests(unittest.TestCase):
    def test_canonical_ids_ignore_tracking_and_reject_unrelated_domains(self):
        self.assertEqual(boards.job_identity('indeed','https://de.indeed.com/rc/clk?jk=abc12345&tracking=1'),
                         boards.job_identity('indeed','https://www.indeed.com/viewjob?vjk=abc12345'))
        self.assertIsNone(boards.job_identity('indeed','https://evil.invalid/viewjob?jk=abc12345'))
        self.assertIsNone(boards.job_identity('indeed','https://de.indeed.com/career/salaries?jk=abc12345'))
        self.assertEqual(boards.job_identity('xing','https://www.xing.com/jobs/munich-test-engineer-123456789?x=1')[0], '123456789')

    def test_xing_overlay_links_and_dedup(self):
        soup=BeautifulSoup('<a href="/jobs/munich-test-123456789" aria-label="Test Engineer"></a><a href="/jobs/munich-test-123456789?x=2">Test Engineer</a>', 'html.parser')
        jobs=boards.collect_links('xing',soup)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['title'],'Test Engineer')

    def test_plain_text_section_labels_and_original_city(self):
        data=boards.parse_details(details_html(jobLocationType='TELECOMMUTE'),{'title':''})
        self.assertIn('Munich',data['location'])
        self.assertEqual(len(data['tasks']),1)
        self.assertEqual(len(data['requirements']),1)
        self.assertEqual(len(data['benefits']),1)

    def test_combined_indeed_heading_does_not_mix_tasks_and_requirements(self):
        data=boards.sections('<p>Your role<br>Key responsibilities in your new role</p><ul><li>Run tests</li></ul><p>Your profile<br>Qualifications and skills to help you succeed</p><ul><li>CANoe experience required</li></ul>')
        self.assertEqual(data['tasks'],['Run tests'])
        self.assertEqual(data['requirements'],['CANoe experience required'])

    def test_age_unknown_future_expired_and_old_never_match(self):
        for value in ['',(NOW-timedelta(hours=25)).isoformat(),(NOW+timedelta(hours=1)).isoformat()]:
            d=boards.parse_details(details_html(datePosted=value),{'title':''})
            self.assertEqual(boards.assess({},d,NOW)[0],'reject')
        d=boards.parse_details(details_html(validThrough=(NOW-timedelta(minutes=1)).isoformat()),{'title':''})
        self.assertEqual(boards.assess({},d,NOW)[1]['reason'],'expired')

    def test_original_hard_filters_apply_to_boards(self):
        for overrides in [
            {'title':'Full-Stack Engineer'},
            {'description':'Requirements <ul><li>Experience with FPGA is required.</li></ul>'*3},
            {'description':'Requirements <ul><li>Experience in PCB design is required.</li></ul>'*3},
            {'description':'Requirements <ul><li>Fließende Deutschkenntnisse C1 sind erforderlich.</li></ul>'*3},
            {'jobLocation':{'address':{'addressLocality':'Dresden','addressCountry':'DE'}},
             'description':'Mobiles Arbeiten nach Absprache. Vehicle tests using CANoe and test automation. '*4},
        ]:
            d=boards.parse_details(details_html(**overrides),{'title':''})
            self.assertEqual(boards.assess({'title':d['title']},d,NOW)[0],'reject',overrides)

    def test_claimed_delivered_uncertain_and_suppressed_never_attempt_again(self):
        for status in ('claimed','delivered','uncertain','suppressed'):
            with patch.object(boards,'get_job_record',return_value={'notification_status':status}),patch.object(boards,'fetch_details') as fetch,patch.object(boards,'notify_job_once') as send:
                self.assertEqual(boards.process(None,{'source':'indeed','job_id':'abc12345','title':'Test Engineer'},True)['decision'],'already_reserved')
                fetch.assert_not_called();send.assert_not_called()

    def test_dry_run_cannot_write_or_notify(self):
        with patch.object(boards,'fetch_details',return_value=boards.parse_details(details_html(),{'title':''})),patch.object(boards,'assess',return_value=('manual',{'reason':'uncertain'},75)),patch.object(boards,'save_job') as save,patch.object(boards,'notify_job_once') as send:
            boards.process(None,{'source':'xing','job_id':'123456789','title':'Test Engineer','url':'https://www.xing.com/jobs/test-123456789'})
            save.assert_not_called();send.assert_not_called()

    def test_publication_uses_shared_atomic_notifier(self):
        d=boards.parse_details(details_html(),{'title':''})
        with patch.object(boards,'get_job_record',return_value=None),patch.object(boards,'fetch_details',return_value=d),patch.object(boards,'assess',return_value=('manual',{'reason':'uncertain'},75)),patch.object(boards,'save_job'),patch.object(boards,'update_job'),patch.object(boards,'record_decision'),patch.object(boards,'notify_job_once',return_value=True) as send:
            r=boards.process(None,{'source':'xing','job_id':'123456789','title':'Test Engineer','url':'https://www.xing.com/jobs/test-123456789'},True)
            self.assertTrue(r['sent']);self.assertEqual(send.call_count,1)

    def test_blocked_source_stops_after_one_request_and_reports_status(self):
        error=boards.requests.HTTPError(response=Mock(status_code=403))
        with patch.object(boards,'fetch_html',side_effect=error) as fetch,patch.object(boards.time,'sleep'):
            report=boards.run('indeed',queries=['Test Engineer','Validation Engineer'])
        self.assertFalse(report['healthy'])
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(report['search_errors'][0]['http_status'],403)

    def test_missing_description_and_foreign_countries_fail_closed(self):
        with self.assertRaises(ValueError):boards.parse_details(BeautifulSoup('<h1>Job</h1>','html.parser'),{'title':''})
        with self.assertRaises(ValueError):boards.parse_details(details_html(jobLocation={'address':{'addressCountry':'AT'}}),{'title':''})


if __name__=='__main__':unittest.main()
