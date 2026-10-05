"""Pure checks for production health gates and daily monitoring."""
import unittest
from datetime import datetime, timedelta, timezone
from scripts.live_health import assess_log
from scripts.daily_health import verify_runs


class TestLiveSourceHealth(unittest.TestCase):
    def test_bmw_ok(self):
        okay, detail = assess_log(
            "bmw",
            "TOTAL BMW JOBS READ: 54\nSupabase sync failures: 0\nBMW SUPABASE BRIDGE: SUCCESS",
        )
        self.assertTrue(okay, detail)

    def test_bmw_zero_jobs_cannot_pass(self):
        okay, _ = assess_log(
            "bmw",
            "TOTAL BMW JOBS READ: 0\nSupabase sync failures: 0\nBMW SUPABASE BRIDGE: SUCCESS",
        )
        self.assertFalse(okay)

    def test_bmw_database_sync_error_is_failure(self):
        okay, _ = assess_log(
            "bmw",
            "TOTAL BMW JOBS READ: 54\nSupabase sync failures: 1\nBMW SUPABASE BRIDGE: COMPLETED WITH ERRORS",
        )
        self.assertFalse(okay)

    def test_linkedin_five_successful_searches(self):
        log = "TOTAL UNIQUE LINKEDIN JOBS: 40\nLINKEDIN + SUPABASE SUMMARY\n"
        log += "HTTP: 200 | bytes: 33333\n" * 5
        okay, detail = assess_log("linkedin", log)
        self.assertTrue(okay, detail)

    def test_linkedin_single_429_is_degraded_but_usable(self):
        log = "TOTAL UNIQUE LINKEDIN JOBS: 30\nLINKEDIN + SUPABASE SUMMARY\n"
        log += "HTTP: 200 | bytes: 33333\n" * 4 + "HTTP: 429 | bytes: 0\n"
        okay, detail = assess_log("linkedin", log)
        self.assertTrue(okay, detail)
        self.assertTrue(detail.startswith("DEGRADED:"))

    def test_linkedin_two_429s_are_failure(self):
        log = "TOTAL UNIQUE LINKEDIN JOBS: 20\nLINKEDIN + SUPABASE SUMMARY\n"
        log += "HTTP: 200 | bytes: 33333\n" * 3 + "HTTP: 429 | bytes: 0\n" * 2
        okay, _ = assess_log("linkedin", log)
        self.assertFalse(okay)

    def test_linkedin_single_non_429_failure_is_failure(self):
        log = "TOTAL UNIQUE LINKEDIN JOBS: 30\nLINKEDIN + SUPABASE SUMMARY\n"
        log += "HTTP: 200 | bytes: 33333\n" * 4 + "HTTP: 403 | bytes: 0\n"
        okay, _ = assess_log("linkedin", log)
        self.assertFalse(okay)

    def test_optional_remote_http_does_not_change_local_health_count(self):
        log = "TOTAL UNIQUE LINKEDIN JOBS: 40\nLINKEDIN + SUPABASE SUMMARY\n"
        log += "HTTP: 200 | bytes: 33333\n" * 5
        log += "  REMOTE HTTP: 429 | bytes: 0\n"
        okay, detail = assess_log("linkedin", log)
        self.assertTrue(okay, detail)


class TestDailyStatus(unittest.TestCase):
    @staticmethod
    def sample_run(at, result="success"):
        return {"created_at": at.isoformat(), "status": "completed",
                "head_branch": "main", "conclusion": result}

    def test_recent_running_monitors(self):
        now = datetime.now(timezone.utc)
        ok, _ = verify_runs([
            self.sample_run(now-timedelta(minutes=2)),
            self.sample_run(now-timedelta(minutes=7)),
        ], now)
        self.assertTrue(ok)

    def test_two_failures_raise_health_issue(self):
        now = datetime.now(timezone.utc)
        ok, _ = verify_runs([
            self.sample_run(now-timedelta(minutes=2), "failure"),
            self.sample_run(now-timedelta(minutes=7), "failure"),
        ], now)
        self.assertFalse(ok)

    def test_no_recent_run_is_an_issue(self):
        now = datetime.now(timezone.utc)
        ok, _ = verify_runs([self.sample_run(now-timedelta(hours=2))], now)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
