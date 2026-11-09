"""Deterministic tests for future week, overdue, duplicates and missing QA."""
import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from automation.verify_readiness import (audit, target_week, month_budget, ZONE,
                                        YOUTUBE_CHANNEL, metadata_digest, release_check)

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
        self.save("automation/publisher-status.json",
                  {"updated_at": "2026-11-15T10:15:00+01:00"})
        self.assertTrue(audit(self.root, t)["ok"])


class YouTubeReadinessTests(ReadinessTests):
    def setUp(self):
        super().setUp()
        config = json.loads((self.root / "automation/config.json").read_text())
        config["youtube"] = {"enabled": True, "channel_id": YOUTUBE_CHANNEL,
                             "weekly_shorts": 1, "source_slot": "tuesday",
                             "made_for_kids": False, "privacy": "PUBLIC"}
        self.save("automation/config.json", config)
        self.save("automation/publisher-status.json", {
            "updated_at": "2026-11-16T09:20:00+01:00",
            "quota": {"observed_at": "2026-11-16T09:20:00+01:00",
                      "observed_used": 3, "month": "2026-11",
                      "observed_published_post_ids": [],
                      "observation_basis": "Metricool planner counter"}})
        posts = self.readposts()
        short = self.post("TT-101-YOUTUBE-SHORT", "TT-101", "SHORT", DATES[0])
        short.update(platform="youtube", source_post_id="TT-101-REEL",
                     youtube_channel_id=YOUTUBE_CHANNEL,
                     youtube={"title": "A scientific story | Toxic Tales",
                              "description": "Research: 10.1111/TT-101\n"
                              "https://akshaymohan16.github.io/toxic-tales-library/sources/tt-101.html",
                              "made_for_kids": False, "privacy": "PUBLIC",
                              "is_ai_generated": True,
                              "review_decision": "pass", "rights_review_decision": "pass",
                              "reviewed_release_fingerprint": "fp-TT-101",
                              "source_video_sha256": "sha-TT-101"})
        short["youtube"]["metadata_sha256"] = metadata_digest(short)
        short["metricool_media_urls"] = ["https://static.metricool.com/planner/tt-101.mp4"]
        short["metricool_media_sha256"] = {short["metricool_media_urls"][0]: "sha-TT-101"}
        short["schedule_readback_verified"] = True
        short["provider_readback_checked_at"] = "2026-11-16T09:20:00+01:00"
        short["provider_readback"] = {
            "id": short["metricool_id"], "uuid": short["metricool_uuid"],
            "text": short["youtube"]["description"], "media": short["metricool_media_urls"],
            "providers": [{"network": "youtube", "status": "PENDING"}],
            "autoPublish": True, "draft": False,
            "publicationDate": {"dateTime": "2026-11-17T10:00:00", "timezone": "Europe/Vienna"},
            "youtubeData": {"title": short["youtube"]["title"], "type": "short",
                            "privacy": "public", "madeForKids": False,
                            "isAiGeneratedContent": True}}
        posts.append(short)
        self.save("automation/published.json", {"posts": posts})

    def test_complete_monday_passes(self):
        report = self.check()
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(len(report["slots"]), 4)
        self.assertEqual(report["monthly_budgets"][0]["published_used"], 3)
        self.assertEqual(report["monthly_budgets"][0]["unfilled_instagram_reservations"], 3)

    def test_overdue_requires_real_publication_receipt(self):
        posts = self.readposts()
        posts[0].update(status="published", provider_status="PUBLISHED",
                        public_url="https://www.instagram.com/reel/verified/")
        posts[3].update(status="published", provider_status="PUBLISHED",
                        public_url="https://www.youtube.com/shorts/abcdefghijk")
        posts[3]["provider_readback"]["providers"] = [{
            "network": "youtube", "status": "PUBLISHED", "publicUrl": posts[3]["public_url"]}]
        self.save("automation/published.json", {"posts": posts})
        report = self.check("2026-11-17T14:15:00+01:00")
        self.assertFalse(report["ok"])
        self.assertIn("live video/channel verification missing", " ".join(report["errors"]))
        posts[3]["live_verification"] = {
            "checked_at": "2026-11-17T10:15:00+01:00", "decision": "pass",
            "channel_id": YOUTUBE_CHANNEL, "url": posts[3]["public_url"]}
        self.save("automation/published.json", {"posts": posts})
        report = self.check("2026-11-17T14:15:00+01:00")
        self.assertTrue(report["ok"], report["errors"])

    def test_missing_youtube_fails_without_hiding_instagram(self):
        self.save("automation/published.json", {"posts": self.readposts()[:3]})
        report = self.check()
        self.assertFalse(report["ok"])
        self.assertIn("tuesday_youtube", " ".join(report["errors"]))
        self.assertEqual([r["post_id"] for r in report["slots"][:3]],
                         ["TT-101-REEL", "TT-101-CAROUSEL", "TT-102-REEL"])

    def test_provider_utc_z_timestamp_is_valid(self):
        posts = self.readposts()
        posts[3]["provider_readback_checked_at"] = "2026-11-16T08:20:00Z"
        self.save("automation/published.json", {"posts": posts})
        self.assertTrue(self.check()["ok"], self.check()["errors"])

    def test_same_video_on_two_networks_is_allowed_but_duplicate_youtube_is_not(self):
        self.assertTrue(self.check()["ok"])
        posts = self.readposts()
        posts.append({**posts[3], "post_id": "DUPLICATE", "metricool_uuid": "different"})
        self.save("automation/published.json", {"posts": posts})
        errors = " ".join(self.check()["errors"])
        self.assertIn("Duplicate DOI+video within youtube", errors)
        self.assertIn("Duplicate video bytes within youtube", errors)

    def test_wrong_channel_or_source_cannot_release_short(self):
        for key, value in (("youtube_channel_id", "different-channel"),
                           ("source_post_id", "TT-102-REEL")):
            with self.subTest(key=key):
                posts = self.readposts()
                original = posts[3][key]
                posts[3][key] = value
                self.save("automation/published.json", {"posts": posts})
                self.assertFalse(self.check()["ok"])
                posts[3][key] = original
                self.save("automation/published.json", {"posts": posts})

    def test_wrong_audience_privacy_or_stale_rights_review_blocks(self):
        for key, value in (("made_for_kids", True), ("privacy", "PRIVATE"),
                           ("rights_review_decision", "pending"),
                           ("reviewed_release_fingerprint", "stale"),
                           ("source_video_sha256", "stale"),
                           ("title", ""), ("description", "No citation")):
            with self.subTest(key=key):
                posts = self.readposts()
                original = posts[3]["youtube"][key]
                posts[3]["youtube"][key] = value
                self.save("automation/published.json", {"posts": posts})
                self.assertFalse(self.check()["ok"])
                posts[3]["youtube"][key] = original
                self.save("automation/published.json", {"posts": posts})

    def test_saturday_youtube_is_not_an_extra_slot(self):
        posts = self.readposts()
        posts[3]["publication_date"] = DATES[2]
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("Tuesday 10:00 slot", " ".join(self.check()["errors"]))

    def test_changed_description_invalidates_metadata_review(self):
        posts = self.readposts()
        posts[3]["youtube"]["description"] += " New claim."
        posts[3]["provider_readback"]["text"] = posts[3]["youtube"]["description"]
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("metadata changed since its review", " ".join(self.check()["errors"]))

    def test_synthetic_disclosure_removal_or_provider_mismatch_blocks(self):
        for value in (None, False):
            with self.subTest(value=value):
                posts = self.readposts()
                if value is None:
                    posts[3]["youtube"].pop("is_ai_generated")
                else:
                    posts[3]["youtube"]["is_ai_generated"] = value
                self.save("automation/published.json", {"posts": posts})
                errors = " ".join(self.check()["errors"])
                self.assertIn("synthetic-media disclosure missing", errors)
                self.assertIn("metadata changed since its review", errors)
                posts[3]["youtube"]["is_ai_generated"] = True
                self.save("automation/published.json", {"posts": posts})
        posts = self.readposts()
        posts[3]["provider_readback"]["youtubeData"]["isAiGeneratedContent"] = False
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("provider readback does not match", " ".join(self.check()["errors"]))
        del posts[3]["provider_readback"]["youtubeData"]["isAiGeneratedContent"]
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("provider readback does not match", " ".join(self.check()["errors"]))

    def test_youtube_item_cannot_include_instagram_destination(self):
        posts = self.readposts()
        posts[3]["provider_readback"]["providers"].append({"network": "instagram", "status": "PENDING"})
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("provider readback does not match", " ".join(self.check()["errors"]))

    def test_readback_settings_or_hosted_bytes_mismatch_fails(self):
        for key, value in (("madeForKids", True), ("title", "Different"), ("privacy", "private")):
            with self.subTest(key=key):
                posts = self.readposts()
                original = posts[3]["provider_readback"]["youtubeData"][key]
                posts[3]["provider_readback"]["youtubeData"][key] = value
                self.save("automation/published.json", {"posts": posts})
                self.assertIn("provider readback does not match", " ".join(self.check()["errors"]))
                posts[3]["provider_readback"]["youtubeData"][key] = original
                self.save("automation/published.json", {"posts": posts})
        posts = self.readposts()
        posts[3]["metricool_media_sha256"] = {}
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("hosted YouTube media hash verification missing", " ".join(self.check()["errors"]))

    def test_future_week_duplicate_is_caught_on_sunday(self):
        posts = self.readposts()
        posts.append({**posts[3], "post_id": "UNCERTAIN-SECOND",
                      "status": "submission_uncertain", "publication_date": "2026-11-24T10:00:00+01:00"})
        posts.append({**posts[3], "post_id": "UNCERTAIN-THIRD",
                      "status": "submission_uncertain", "publication_date": "2026-11-24T10:00:00+01:00"})
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("More than one YouTube destination reserved", " ".join(self.check()["errors"]))

    def test_bad_source_date_or_files_reports_failure_without_crashing(self):
        for key, value in (("publication_date", "nonsense"), ("source_files_sha256", None)):
            with self.subTest(key=key):
                posts = self.readposts()
                original = posts[0][key]
                posts[0][key] = value
                self.save("automation/published.json", {"posts": posts})
                self.assertFalse(self.check()["ok"])
                posts[0][key] = original
                self.save("automation/published.json", {"posts": posts})

    def test_published_without_a_real_video_url_fails(self):
        posts = self.readposts()
        posts[3].update(status="published", provider_status="PUBLISHED",
                        public_url="https://www.youtube.com/channel/" + YOUTUBE_CHANNEL)
        posts[3]["provider_readback"]["providers"] = [{
            "network": "youtube", "status": "PUBLISHED", "publicUrl": posts[3]["public_url"]}]
        posts[3]["live_verification"] = {
            "checked_at": "2026-11-17T10:15:00+01:00", "decision": "pass",
            "channel_id": YOUTUBE_CHANNEL, "url": posts[3]["public_url"]}
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("missing PUBLISHED status/live URL", " ".join(self.check()["errors"]))

    def test_counter_missing_stale_or_wrong_month_fails(self):
        for observed_at, month in (("2026-11-12T10:00:00+01:00", "2026-11"),
                                    ("2026-11-16T09:20:00+01:00", "2026-10")):
            self.save("automation/publisher-status.json", {
                "updated_at": "2026-11-16T09:20:00+01:00",
                "quota": {"observed_used": 3, "observed_at": observed_at,
                          "observed_published_post_ids": [],
                          "month": month, "observation_basis": "Metricool planner counter"}})
            self.assertIn("planner counter observation required", " ".join(self.check()["errors"]))

    def test_cap_includes_remaining_unscheduled_instagram_dates(self):
        state = json.loads((self.root / "automation/publisher-status.json").read_text())
        state["quota"]["observed_used"] = 14
        self.save("automation/publisher-status.json", state)
        report = self.check()
        self.assertEqual(report["monthly_budgets"][0]["projected"], 21)
        self.assertFalse(report["ok"])
        self.assertIn("protected remaining Instagram", " ".join(report["errors"]))

    def test_rejected_episode_cannot_be_revived_on_youtube(self):
        posts = self.readposts()
        posts[3]["episode_id"] = "TT-003"
        self.save("automation/published.json", {"posts": posts})
        self.assertIn("Rejected TT-003", " ".join(self.check()["errors"]))

    def test_sunday_preproduction_suppressed(self):
        # Sunday can be missing next week's Short, but actual existing receipts
        # and today's provider counter must still pass their safety checks.
        self.save("automation/published.json", {"posts": self.readposts()[:3]})
        self.save("automation/publisher-status.json", {
            "updated_at": "2026-11-15T10:15:00+01:00",
            "quota": {"observed_used": 3, "observed_at": "2026-11-15T10:15:00+01:00",
                      "observed_published_post_ids": [],
                      "month": "2026-11", "observation_basis": "Metricool planner counter"}})
        self.assertTrue(self.check("2026-11-15T12:00:00+01:00")["ok"])


class MotionReadinessTests(ReadinessTests):
    def setUp(self):
        super().setUp()
        # Use the same canonical hash helpers as the rendering pipeline; the
        # watchdog itself intentionally requires only Python's standard library.
        from scripts.editorial_gate import editorial_source_sha256
        from scripts.motion_spec import motion_spec_sha256
        episode = json.loads((self.root / "episodes/tt-101.json").read_text())
        evidence = self.root / episode["evidence_file"]
        evidence_sha = hashlib.sha256(evidence.read_bytes()).hexdigest()
        episode["script_author"] = "test script author"
        episode["production"].update(renderer="nature-motion-10",
            editorial_style="science-journalism", editorial_standard="story-first-v1",
            motion={"schema_version": 1, "evidence_sha256": evidence_sha})
        self.save("episodes/tt-101.json", episode)
        self.save("assets/branding/toxic-tales-logo.json", {"sha256": "approved-logo-sha"})
        releases = json.loads((self.root / "quality/releases.json").read_text())
        release = releases["TT-101"]
        release["evidence_sha256"] = evidence_sha
        source_sha = editorial_source_sha256(episode, evidence.read_text(encoding="utf-8"))
        identity = {key: copy.deepcopy(release[key]) for key in
                    ("fingerprint", "files", "evidence_sha256")}
        for key, standard in (("final_editorial_review", "story-first-v1"),
                               ("branding_review", "toxic-tales-branding-v1"),
                               ("motion_review", "toxic-tales-motion-v1")):
            release[key] = {**identity, "standard": standard, "decision": "pass",
                            "reviewer": "independent final export reviewer",
                            "reviewed_at": "2026-11-16T09:00:00+01:00",
                            "independent_from_script_author": True,
                            "reviewed_encoded_frames": True}
        release["final_editorial_review"]["source_sha256"] = source_sha
        release["branding_review"].update(logo_sha256="approved-logo-sha",
            **{key: True for key in ("reviewed_opening_frames", "reviewed_every_shot_and_transition",
                    "reviewed_final_frame", "reviewed_cover", "reviewed_phone_scale")})
        release["motion_review"].update(source_sha256=source_sha,
            motion_spec_sha256=motion_spec_sha256(episode),
            reviewed_every_shot_and_transition=True, reviewed_phone_scale=True,
            checks={key: {"decision": "pass", "finding": "Specific rendered observation",
                           "basis": "Exact encoded frame and original evidence record"}
                    for key in ("kinetic_text", "transitions", "ecological_motion",
                                "camera_motion", "evidence_bound_data", "caption_sync")})
        self.save("quality/releases.json", releases)

    def test_motion_receipts_pass_for_both_reel_and_short(self):
        self.assertTrue(self.check()["ok"], self.check()["errors"])
        releases = json.loads((self.root / "quality/releases.json").read_text())
        receipt = self.readposts()[0]
        for fmt in ("REEL", "SHORT"):
            errors = []
            release_check(self.root, {**receipt, "format": fmt}, releases, errors)
            self.assertEqual(errors, [])

    def test_motion_missing_stale_and_nonindependent_reviews_fail(self):
        releases = json.loads((self.root / "quality/releases.json").read_text())
        for review in ("final_editorial_review", "branding_review", "motion_review"):
            for key, value in (("decision", "hold"), ("files", {}),
                               ("fingerprint", "stale"), ("evidence_sha256", "stale"),
                               ("independent_from_script_author", False),
                               ("reviewer", "test script author")):
                altered = copy.deepcopy(releases)
                altered["TT-101"][review][key] = value
                self.save("quality/releases.json", altered)
                with self.subTest(review=review, field=key):
                    self.assertIn("motion film lacks current", " ".join(self.check()["errors"]))
        for key in ("source_sha256", "motion_spec_sha256"):
            altered = copy.deepcopy(releases)
            altered["TT-101"]["motion_review"][key] = "stale"
            self.save("quality/releases.json", altered)
            with self.subTest(motion_identity=key):
                self.assertFalse(self.check()["ok"])

    def test_motion_changed_source_evidence_logo_or_missing_observations_fail(self):
        source = self.root / "episodes/tt-101.json"
        episode = json.loads(source.read_text())
        changed = copy.deepcopy(episode)
        changed["production"]["new_claim"] = "Unreviewed source edit"
        self.save("episodes/tt-101.json", changed)
        self.assertFalse(self.check()["ok"])
        self.save("episodes/tt-101.json", episode)
        evidence = self.root / episode["evidence_file"]
        original = evidence.read_bytes()
        evidence.write_bytes(original + b"changed evidence")
        self.assertFalse(self.check()["ok"])
        evidence.write_bytes(original)
        self.save("assets/branding/toxic-tales-logo.json", {"sha256": "different-logo"})
        self.assertFalse(self.check()["ok"])
        self.save("assets/branding/toxic-tales-logo.json", {"sha256": "approved-logo-sha"})
        releases = json.loads((self.root / "quality/releases.json").read_text())
        releases["TT-101"]["motion_review"]["checks"]["evidence_bound_data"]["finding"] = "pass"
        self.save("quality/releases.json", releases)
        self.assertFalse(self.check()["ok"])


class MonthlyBudgetTests(unittest.TestCase):
    def test_publications_after_counter_snapshot_add_to_external_usage(self):
        now = datetime.fromisoformat("2026-11-30T11:00:00+01:00")
        posts = [{"post_id": "post-" + str(i), "platform": "instagram",
                  "publication_date": "2026-11-07T10:00:00+01:00", "status": "published"}
                 for i in range(5)]
        baseline = ["instagram:post-" + str(i) for i in range(3)]
        report = month_budget(posts, now, 2026, 11, observed_used=5,
                              observed_published_keys=baseline)
        self.assertEqual(report["projected"], 7)

    def test_provider_counter_does_not_double_count_published_receipts(self):
        now = datetime.fromisoformat("2026-11-16T11:00:00+01:00")
        posts = [{"publication_date": "2026-11-07T10:00:00+01:00",
                  "status": "published", "platform": "instagram", "format": "REEL"}]
        report = month_budget(posts, now, 2026, 11, observed_used=3)
        self.assertEqual(report["published_used"], 3)
        self.assertEqual(report["unfilled_instagram_reservations"], 6)
        self.assertEqual(report["projected"], 9)

    def test_two_destinations_and_uncertain_writes_each_reserve_capacity(self):
        now = datetime.fromisoformat("2026-11-30T11:00:00+01:00")
        posts = [{"publication_date": "2026-11-24T10:00:00+01:00", "status": status,
                  "platform": network, "format": fmt}
                 for status, network, fmt in (("published", "instagram", "REEL"),
                                              ("published", "youtube", "SHORT"),
                                              ("submission_uncertain", "youtube", "SHORT"))]
        report = month_budget(posts, now, 2026, 11, observed_used=2)
        self.assertEqual(report["projected"], 3)

    def test_future_month_protects_all_instagram_slots(self):
        now = datetime.fromisoformat("2026-11-30T11:00:00+01:00")
        report = month_budget([], now, 2026, 12)
        self.assertEqual(report["unfilled_instagram_reservations"], 14)
        self.assertEqual(report["projected"], 14)

    def test_dst_month_uses_vienna_wall_clock(self):
        now = datetime.fromisoformat("2027-03-01T08:00:00+01:00")
        due = datetime(2027, 3, 30, 10, tzinfo=ZONE).isoformat()
        posts = [{"publication_date": due, "status": "scheduled", "format": "REEL"}]
        report = month_budget(posts, now, 2027, 3)
        self.assertEqual(report["unfilled_instagram_reservations"], 12)
        self.assertEqual(report["projected"], 13)


if __name__ == "__main__":
    unittest.main()
