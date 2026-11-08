"""Deterministic tests for future week, overdue, duplicates and missing QA."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from automation.verify_readiness import audit, target_week

DATES = ["2026-11-17T10:00:00+01:00", "2026-11-19T10:00:00+01:00",
         "2026-11-21T10:00:00+01:00"]


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.save("automation/config.json", {
            "allowed_repository": "akshaymohan16/toxic-tales-library",
            "metricool_brand_id": "7937614", "timezone": "Europe/Vienna",
            "publishing_paused": False, "monthly_publication_cap": 20})
        self.save("automation/publisher-status.json", {
            "updated_at": "2026-11-16T09:20:00+01:00"})
        releases = {}
        for ep in ("TT-101", "TT-102"):
            self.save("episodes/" + ep.lower() + ".json",
                      {"id": ep, "doi": "10.1111/" + ep,
                       "evidence_file": "evidence/" + ep.lower() + ".md",
                       "production": {"renderer": "nature-branded-9"}})
            file = self.root / "evidence" / (ep.lower() + ".md")
            file.parent.mkdir(exist_ok=True)
            file.write_text("Full original paper record", encoding="utf-8")
            releases[ep] = {
                "decision": "release", "fingerprint": "fp-" + ep,
                "files": {"media/" + ep + ".mp4": "sha-" + ep},
                "final_editorial_review": {"decision": "pass"},
                "branding_review": {"decision": "pass"}}
        self.save("quality/releases.json", releases)
        self.save("automation/published.json", {"posts": [
            self.post("TT-101-REEL", "TT-101", "REEL", DATES[0]),
            self.post("TT-101-CAROUSEL", "TT-101", "CAROUSEL", DATES[1]),
            self.post("TT-102-REEL", "TT-102", "REEL", DATES[2])]})

    def save(self, rel, value):
        file = self.root / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(value), encoding="utf-8")

    def post(self, pid, ep, fmt, date):
        return {"post_id": pid, "episode_id": ep, "doi": "10.1111/" + ep,
                "format": fmt, "publication_date": date, "status": "scheduled",
                "provider_status": "PENDING", "metricool_id": pid,
                "metricool_uuid": "uuid-" + pid,
                "planner_url": "https://app.metricool.com/planner?id=" + pid,
                "auto_publish": True, "draft": False,
                "release_fingerprint": "fp-" + ep,
                "source_files_sha256": {"media/" + ep + ".mp4": "sha-" + ep}}

    def readposts(self):
        return json.loads((self.root / "automation/published.json").read_text())["posts"]

    def check(self, instant="2026-11-16T11:00:00+01:00"):
        return audit(self.root, datetime.fromisoformat(instant))

    def test_complete_monday_passes(self):
        self.assertTrue(self.check()["ok"], self.check()["errors"])
        self.assertEqual(len(self.check()["slots"]), 3)

    def test_missing_saturday_fails(self):
        self.save("automation/published.json", {"posts": self.readposts()[:2]})
        self.assertFalse(self.check()["ok"])
        self.assertIn("saturday", " ".join(self.check()["errors"]))

    def test_overdue_requires_real_publication_receipt(self):
        self.assertFalse(self.check("2026-11-17T14:15:00+01:00")["ok"])
        p = self.readposts()
        p[0].update(status="published", provider_status="PUBLISHED",
                    public_url="https://www.instagram.com/reel/verified/")
        self.save("automation/published.json", {"posts": p})
        self.assertTrue(self.check("2026-11-17T14:15:00+01:00")["ok"])

    def test_duplicate_doi_and_time_fail(self):
        p = self.readposts()
        p.append({**p[0], "post_id": "TT-101-REEL-B", "metricool_uuid": "fresh-uuid"})
        self.save("automation/published.json", {"posts": p})
        self.assertFalse(self.check()["ok"])

    def test_stale_publisher_fails(self):
        self.save("automation/publisher-status.json",
                  {"updated_at": "2026-11-12T10:00:00+01:00"})
        self.assertFalse(self.check()["ok"])

    def test_media_mismatch_fails(self):
        p = self.readposts()
        p[0]["source_files_sha256"]["media/TT-101.mp4"] = "wrong"
        self.save("automation/published.json", {"posts": p})
        self.assertFalse(self.check()["ok"])

    def test_sunday_preproduction_suppressed(self):
        t = datetime.fromisoformat("2026-11-15T12:00:00+01:00")
        self.assertIsNone(target_week(t))
        self.assertTrue(audit(self.root, t)["ok"])


if __name__ == "__main__":
    unittest.main()
