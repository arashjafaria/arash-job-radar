import unittest
from unittest.mock import Mock, patch
import supabase_store as store
import linkedin_monitor as linkedin

class HistoryBatchTests(unittest.TestCase):
    def test_two_requests_for_150_jobs_and_no_descriptions(self):
        responses = [Mock(status_code=200), Mock(status_code=200)]
        responses[0].json.return_value = [{"job_id": "1", "status": "sent"}]
        responses[1].json.return_value = []
        with patch.object(store, '_check_config'), patch.object(store, '_request', side_effect=responses) as request:
            rows = store.get_job_records('linkedin', range(150))
        self.assertEqual(2, request.call_count)
        self.assertEqual('sent', rows['1']['status'])
        self.assertNotIn('description', request.call_args.kwargs['params']['select'])

    def test_snapshot_preserves_sent_job_and_unknown_job_behavior(self):
        with patch.object(linkedin, 'TEST_MODE', False), patch.object(linkedin, 'get_job_record', side_effect=AssertionError('extra lookup')):
            self.assertTrue(linkedin.already_seen({'job_id': '1'}, {'1': {'job_id': '1', 'status': 'sent'}}))
            self.assertFalse(linkedin.already_seen({'job_id': '2'}, {}))

    def test_batch_database_error_stops_instead_of_treating_everything_as_new(self):
        with patch.object(store, '_check_config'), patch.object(store, '_request', return_value=Mock(status_code=503)):
            with self.assertRaises(RuntimeError):
                store.get_job_records('linkedin', ['1'])
