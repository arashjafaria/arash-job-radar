"""Real PostgreSQL tests; run against an EMPTY disposable database only.

Set RADAR_TEST_DATABASE_URL to opt in. No live Supabase or Telegram calls.
"""
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import unittest

DSN = os.getenv("RADAR_TEST_DATABASE_URL")


@unittest.skipUnless(DSN, "requires a disposable PostgreSQL database")
class TestNotificationDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.psycopg = psycopg
        with psycopg.connect(DSN, autocommit=True) as db:
            if db.execute("SELECT to_regclass('public.arash_jobs')").fetchone()[0]:
                raise RuntimeError("Tests require an empty disposable database; refusing to overwrite tables")
            db.execute("CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role")
            db.execute("""CREATE TABLE public.arash_jobs (
                id bigserial PRIMARY KEY, source text NOT NULL, job_id text NOT NULL,
                title text, company text, location text, url text, posted_at timestamptz,
                match_score integer, status text, sent_to_telegram boolean DEFAULT false,
                UNIQUE(source, job_id))""")
            db.execute("""INSERT INTO public.arash_jobs(source,job_id,title,company,location,url,status)
                       VALUES ('linkedin','legacy-digest','Legacy role','Legacy','Munich','https://legacy.invalid','review_digest_sent@old')""")
            cls.sql = (Path(__file__).parents[1] / "migrations/20261011_decisions_and_notifications.sql").read_text()
            db.execute(cls.sql)
            db.execute((Path(__file__).parents[1] / 'supabase/migrations/20261021084241_alten_cross_source_notifications.sql').read_text())
            db.execute((Path(__file__).parents[1] / 'supabase/migrations/20261029003010_ferchau_cross_source_notifications.sql').read_text())

            db.execute((Path(__file__).parents[1] / 'scripts/allow_linkedin_reposts.sql').read_text())
            db.execute((Path(__file__).parents[1] / 'scripts/board_url_keys.sql').read_text())

    def setUp(self):
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute("DELETE FROM public.arash_jobs WHERE job_id <> 'legacy-digest'")
            db.execute("DELETE FROM public.arash_notification_history WHERE job_id <> 'legacy-digest'")
            db.execute((Path(__file__).parents[1] / 'scripts/allow_linkedin_reposts.sql').read_text())
            db.execute((Path(__file__).parents[1] / 'scripts/board_url_keys.sql').read_text())

    def add_job(self, source="linkedin", job_id="same-id", title="Test Engineer", company="Example GmbH", location="Munich"):
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute("INSERT INTO public.arash_jobs(source,job_id,title,company,location,url,status) VALUES (%s,%s,%s,%s,%s,%s,'apply')",
                       (source, job_id, title, company, location, "https://example.invalid/" + source + "/" + job_id))

    def claim(self, source, job_id, token):
        with self.psycopg.connect(DSN, autocommit=True) as db:
            return db.execute("SELECT public.claim_job_notification(%s,%s,%s)", (source, job_id, token)).fetchone()[0]

    def finish(self, token, delivered):
        with self.psycopg.connect(DSN, autocommit=True) as db:
            return db.execute("SELECT public.finish_job_notification('linkedin','same-id',%s,%s)", (token, delivered)).fetchone()[0]

    def test_indeed_distinct_query_ids_and_tracking_variants(self):
        with self.psycopg.connect(DSN, autocommit=True) as db:
            key = lambda url: db.execute("SELECT public.job_notification_key(%s,'url')", (url,)).fetchone()[0]
            self.assertEqual(key('https://de.indeed.com/viewjob?jk=abc12345&from=email'),
                             key('https://www.indeed.com/rc/clk?x=1&jk=abc12345'))
            self.assertNotEqual(key('https://de.indeed.com/viewjob?jk=abc12345'),
                                key('https://de.indeed.com/viewjob?jk=def67890'))
        self.add_job('indeed', 'abc12345', title='Test Engineer')
        self.add_job('indeed', 'def67890', title='Validation Engineer')
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute("UPDATE public.arash_jobs SET url='https://de.indeed.com/viewjob?jk=' || job_id WHERE source='indeed'")
        self.assertTrue(self.claim('indeed', 'abc12345', 'one'))
        self.assertTrue(self.claim('indeed', 'def67890', 'two'))
        self.assertFalse(self.claim('indeed', 'abc12345', 'retry'))

    def test_new_linkedin_posting_id_with_same_title_is_allowed(self):
        self.add_job(job_id="old")
        self.assertTrue(self.claim("linkedin", "old", "a"))
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute("SELECT public.finish_job_notification('linkedin','old','a',true)")
        self.add_job(job_id="new")
        self.assertTrue(self.claim("linkedin", "new", "b"))
        self.assertFalse(self.claim("linkedin", "old", "another"))

    def test_old_suppression_can_be_reassessed_without_releasing_a_delivery(self):
        self.add_job(job_id="old")
        self.assertTrue(self.claim("linkedin", "old", "old-token"))
        self.add_job(job_id="new")
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute("""INSERT INTO public.arash_notification_history(source,job_id,token,title_key,company_key,location_key,url_key,outcome)
                SELECT source,job_id,'previous',public.job_notification_key(title,'title'),public.job_notification_key(company,'company'),public.job_notification_key(location,'location'),public.job_notification_key(url,'url'),'suppressed'
                FROM public.arash_jobs WHERE source='linkedin' AND job_id='new'""")
        self.assertTrue(self.claim("linkedin", "new", "fresh-token"))
        self.assertFalse(self.claim("linkedin", "new", "another"))

    def test_concurrent_same_job_has_exactly_one_winner(self):
        self.add_job()
        with ThreadPoolExecutor(max_workers=8) as workers:
            outcomes = list(workers.map(lambda i: self.claim('linkedin','same-id',str(i)), range(8)))
        self.assertEqual(1, outcomes.count(True))

    def test_concurrent_cross_source_same_vacancy_has_one_winner(self):
        self.add_job()
        self.add_job("bmw", "other-id", company="Example AG", location="Munich, Bavaria, Germany")
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(lambda args: self.claim(*args),
                                       [('linkedin','same-id','a'),('bmw','other-id','b')]))
        self.assertEqual(1, outcomes.count(True))

    def test_concurrent_alten_alias_and_suffix_has_one_winner(self):
        self.add_job('linkedin', 'li-alten', title='System Test Engineer (all gender) gg', company='ALTEN Consulting Services GmbH')
        self.add_job('alten', 'web-alten', title='System Test Engineer (all gender)', company='ALTEN', location='Munich, Bavaria, Germany')
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(lambda args: self.claim(*args),
                [('linkedin', 'li-alten', 'a'), ('alten', 'web-alten', 'b')]))
        self.assertEqual(1, outcomes.count(True))

    def test_legacy_digest_backfilled_even_when_old_flag_was_false(self):
        self.assertFalse(self.claim("linkedin", "legacy-digest", "new-token"))
        with self.psycopg.connect(DSN) as db:
            flag = db.execute("SELECT sent_to_telegram FROM arash_jobs WHERE job_id='legacy-digest'").fetchone()[0]
        self.assertTrue(flag)

    def test_concurrent_ferchau_reference_alias_has_one_winner(self):
        self.add_job('linkedin', 'li-ferchau', title='System Engineer', company='FERCHAU GmbH')
        self.add_job('ferchau', 'web-ferchau', title='Systems Integration Engineer', company='FERCHAU')
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute("UPDATE public.arash_jobs SET decision_evidence=jsonb_build_object('description', 'Reference LI54-31505-M') WHERE job_id='li-ferchau'")
            db.execute("UPDATE public.arash_jobs SET decision_evidence=jsonb_build_object('requisition_id', 'FE54-31505-M') WHERE job_id='web-ferchau'")
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(lambda args: self.claim(*args),
                [('linkedin', 'li-ferchau', 'a'), ('ferchau', 'web-ferchau', 'b')]))
        self.assertEqual(1, outcomes.count(True))

    def test_response_lost_before_send_can_retry_same_reservation_token(self):
        self.add_job()
        self.assertTrue(self.claim('linkedin','same-id','owner'))
        self.assertTrue(self.claim('linkedin','same-id','owner'))
        self.assertFalse(self.claim('linkedin','same-id','different-run'))

    def test_uncertain_delivery_blocks_all_future_runs(self):
        self.add_job()
        self.assertTrue(self.claim('linkedin','same-id','owner'))
        self.assertTrue(self.finish('owner', False))
        self.assertFalse(self.claim('linkedin','same-id','owner'))
        self.assertFalse(self.claim('linkedin','same-id','new-run'))

    def test_repost_revision_and_false_flag_cannot_erase_delivery(self):
        self.add_job()
        self.assertTrue(self.claim('linkedin','same-id','owner'))
        self.assertTrue(self.finish('owner', True))
        with self.psycopg.connect(DSN, autocommit=True) as db:
            flag = db.execute("""UPDATE arash_jobs SET posted_at='2026-10-09', status='review_required@new',
                sent_to_telegram=false WHERE job_id='same-id' RETURNING sent_to_telegram""").fetchone()[0]
        self.assertTrue(flag)
        self.assertFalse(self.claim('linkedin','same-id','repost-run'))

    def test_same_role_different_cities_remain_distinct(self):
        self.add_job()
        self.add_job('bmw','other-id',location='Berlin')
        self.assertTrue(self.claim('linkedin','same-id','a'))
        self.assertTrue(self.claim('bmw','other-id','b'))

    def test_migration_can_run_again_without_releasing_claims(self):
        self.add_job()
        self.assertTrue(self.claim('linkedin','same-id','owner'))
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute(self.sql)
        self.assertFalse(self.claim('linkedin','same-id','new-run'))

    def test_notification_history_survives_job_row_recreation(self):
        self.add_job()
        self.assertTrue(self.claim('linkedin','same-id','owner'))
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute("DELETE FROM arash_jobs WHERE job_id='same-id'")
        self.add_job()
        self.assertFalse(self.claim('linkedin','same-id','new-run'))

    def test_unauthenticated_call_is_denied(self):
        with self.psycopg.connect(DSN, autocommit=True) as db:
            db.execute("SET ROLE anon")
            with self.assertRaises(self.psycopg.errors.InsufficientPrivilege):
                db.execute("SELECT public.claim_job_notification('linkedin','same-id','intruder')")


if __name__ == '__main__':
    unittest.main()
