import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import ferchau_monitor as f


def offer(**changes):
    return dict(typeId=3, locationCountryCode="DE", jobTypeId=1, id=486757,
        slug="/de/en/job/486757/systemingenieur", title="System Engineer (m/f/d)",
        locationCity="Munich", locationRegion="Bavaria", number="FE54-31505-M",
        edited=datetime.now(timezone.utc).timestamp(),
        tasks="<ul><li>Validate system requirements and analyse defects</li></ul>",
        requirements="<ul><li>Requirements engineering experience</li><li>DOORS or comparable tools; MATLAB/Simulink is considered an advantage</li></ul>", **changes)


def html(items, schema=None, total=None):
    data = {"Data": {"Offers": items, "OffersCount": {"total": total or len(items)}}}
    if schema:
        data["Head"] = [{"attributes": {"type": "application/ld+json"}, "content": json.dumps(schema)}]
    return "<script>App.Data = " + json.dumps({"ControllerResponse": data}) + ";</script>"


class FerchauTests(unittest.TestCase):
    def test_structured_sections_do_not_depend_on_heading_parser(self):
        job = f.candidate(offer())
        self.assertEqual(1, len(job["tasks"]))
        self.assertEqual(2, len(job["requirements"]))

    def test_foreign_or_non_fulltime_not_collected(self):
        item = offer()
        item["locationCountryCode"] = "PL"
        self.assertIsNone(f.candidate(item))
        item.update(locationCountryCode="DE", jobTypeId=3)
        self.assertIsNone(f.candidate(item))

    def test_actual_date_used_instead_of_recent_edit(self):
        item = offer()
        session = Mock()
        session.get.return_value.text = html([item], {"@type": "JobPosting", "datePosted": "2026-01-01"})
        job = f.fetch_details(session, f.candidate(item))
        self.assertFalse(f.recent(job))

    def test_unknown_publication_fails_closed(self):
        session = Mock()
        session.get.return_value.text = html([offer()])
        with self.assertRaises(ValueError):
            f.fetch_details(session, f.candidate(offer()))

    def test_optional_clause_not_scored_as_mandatory(self):
        job = f.candidate(offer())
        job["posted_at"] = datetime.now(timezone.utc).isoformat()
        with patch.object(f, "evaluate_details", return_value=("manual", {}, 60)) as evaluate:
            _, evidence, _ = f.assess(job)
        scored = evaluate.call_args.args[1]["requirements"]
        self.assertTrue(any("DOORS" in x for x in scored))
        self.assertFalse(any("MATLAB" in x for x in scored))
        self.assertTrue(any("MATLAB" in x for x in evidence["requirements"]))

    def test_linkedin_and_website_reference_alias(self):
        job = f.candidate(offer())
        prior = dict(source="linkedin", job_id="123", title="Different title", location="Munich",
            notification_status="uncertain", decision_evidence={"description": "Reference LI54-31505-M"})
        self.assertTrue(f.duplicate(job, [prior]))
        prior["notification_status"] = None
        self.assertFalse(f.duplicate(job, [prior]))

    def test_reverse_direction_and_company_history_survives_missing_row(self):
        job = f.candidate(offer())
        prior = dict(source="ferchau", job_id=job["job_id"], title=job["title"],
                     location="Munich", notification_status="delivered")
        incoming = {**job, "source": "linkedin", "job_id": "123"}
        self.assertTrue(f.duplicate(incoming, [prior]))

    def test_outside_scope_and_excluded_title_never_fetch_details(self):
        items = []
        for i, (title, city) in enumerate([("System Engineer", "Dresden"), ("IT Engineer", "Munich")]):
            item = offer()
            item.update(id=i, slug=f"/de/en/job/{i}/role", title=title, locationCity=city)
            item["edited"] = 100000000000
            items.append(item)
        session = Mock()
        session.get.return_value.text = html(items)
        report = f.run(session, [], pause=0)
        self.assertEqual(0, report["summary"]["details_checked"])
        self.assertEqual(1, session.get.call_count)

    def test_repeated_pages_abort_before_publication(self):
        session = Mock()
        session.get.return_value.text = html([offer()], total=50)
        with patch.object(f, "fetch_details", return_value={**f.candidate(offer()), "posted_at": "2026-01-01"}):
            with self.assertRaisesRegex(ValueError, "Repeated"):
                f.run(session, [], max_pages=2, pause=0)

    def test_stale_job_cannot_be_published(self):
        job = {**f.candidate(offer()), "posted_at": "2026-01-01", "decision": "manual"}
        with patch.object(f, "save_job") as save, patch.object(f, "notify_job_once") as notify:
            f.publish({"summary": {"messages_sent": 0}, "jobs": [job]}, Mock())
        save.assert_not_called()
        notify.assert_not_called()

    def test_page_limit_fails_closed(self):
        session = Mock()
        session.get.return_value.text = html([offer()], total=50)
        with patch.object(f, "fetch_details", return_value={**f.candidate(offer()), "posted_at": "2026-01-01"}):
            with self.assertRaisesRegex(ValueError, "Page limit"):
                f.run(session, [], max_pages=1, pause=0)


if __name__ == "__main__":
    unittest.main()
