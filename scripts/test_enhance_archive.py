"""Archive links must mean published, and study footage must stay identifiable."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import enhance_archive as archive


class ArchiveEnhancements(unittest.TestCase):
    def setUp(self):
        self.ig = {"episode_id": "TT-006", "post_id": "TT-006-REEL",
                   "status": "published", "provider_status": "PUBLISHED",
                   "public_url": "https://www.instagram.com/reel/Dfji4yhnB6c/"}
        self.yt = {"episode_id": "TT-006", "post_id": "TT-006-YOUTUBE-SHORT",
                   "platform": "youtube", "status": "published",
                   "provider_status": "PUBLISHED", "youtube_channel_id": archive.CHANNEL_ID,
                   "public_url": "https://www.youtube.com/shorts/X333C5Dcxxo",
                   "live_verification": {"decision": "pass", "channel_id": archive.CHANNEL_ID,
                                         "url": "https://www.youtube.com/shorts/X333C5Dcxxo"}}
        self.episode = {"id": "TT-006", "production": {"assets": []}}

    def test_both_confirmed_platforms_appear_once(self):
        result = archive.confirmed_publications([self.ig, self.yt, self.ig], "TT-006")
        self.assertEqual(["instagram", "youtube"], [p["platform"] for p in result])

    def test_pending_failed_and_other_stories_never_become_links(self):
        for changes in ({"status": "scheduled"}, {"provider_status": "PENDING"},
                        {"provider_status": "FAILED"}, {"episode_id": "TT-007"}):
            post = dict(self.ig, **changes)
            self.assertEqual([], archive.confirmed_publications([post], "TT-006"))

    def test_youtube_requires_matching_live_channel_and_url(self):
        for field, value in (("decision", "pending"), ("channel_id", "wrong"),
                             ("url", "https://www.youtube.com/shorts/aaaaaaaaaaa")):
            post = copy.deepcopy(self.yt)
            post["live_verification"][field] = value
            self.assertEqual([], archive.confirmed_publications([post], "TT-006"))

    def test_wrong_provider_and_non_permalink_urls_rejected(self):
        urls = ["javascript:alert(1)", "https://youtube.com.evil.test/shorts/X333C5Dcxxo",
                "https://www.youtube.com/@toxic_tales_eco", "http://www.youtube.com/shorts/X333C5Dcxxo",
                "https://name@www.youtube.com/shorts/X333C5Dcxxo",
                "https://www.youtube.com:443/shorts/X333C5Dcxxo",
                "https://www.youtube.com/shorts/X333C5Dcxxo?next=evil",
                "https://www.youtube.com/shorts/X333C5Dcxxo#fragment"]
        for url in urls:
            self.assertFalse(archive.platform_url(url, "youtube"), url)
        self.assertFalse(archive.platform_url(self.yt["public_url"], "instagram"))

    def test_actual_study_footage_uses_episode_credit_and_escaping(self):
        self.episode["production"]["assets"] = [
            {"media_type": "video/webm", "creator": "Dona & colleagues",
             "changes": "Original supplementary video S1; actual controlled experiment footage."}]
        result = archive.enhance_page("<p>" + archive.OLD_PROVENANCE + "</p><footer>x</footer>",
                                      self.episode, [])
        self.assertNotIn(archive.OLD_PROVENANCE, result)
        self.assertIn("Dona &amp; colleagues", result)
        self.assertIn("actual controlled experiment footage", result)

    def test_reference_assets_do_not_gain_experiment_footage_claim(self):
        result = archive.provenance_note(self.episode)
        self.assertNotIn("Video source", result)
        self.assertNotIn("actual controlled experiment", result)

    def test_repeated_enhancement_is_idempotent_and_withdrawal_removes_links(self):
        pubs = archive.confirmed_publications([self.ig, self.yt], "TT-006")
        first = archive.enhance_page("<p>" + archive.OLD_PROVENANCE + "</p><footer>x</footer>",
                                     self.episode, pubs)
        second = archive.enhance_page(first, self.episode, pubs)
        self.assertEqual(first, second)
        self.assertEqual(1, first.count("Published versions"))
        withdrawn = archive.enhance_page(first, self.episode, [])
        self.assertNotIn("Published versions", withdrawn)

    def test_post_build_changes_only_pages_and_papers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contents = {
                "episodes/tt-006.json": json.dumps(self.episode),
                "automation/published.json": json.dumps({"posts": [self.ig, self.yt]}),
                "automation/config.json": json.dumps({"active_pilot_id": "TT-006"}),
                "site/papers.json": json.dumps([{"id": "TT-006"}]),
                "site/sources/tt-006.html": "<p>" + archive.OLD_PROVENANCE + "</p><footer>x</footer>",
                "site/pilot-tt-006.html": "<footer>x</footer>",
                "site/pilot.html": "<footer>x</footer>",
                "site/media/tt-006.mp4": "frozen-media-bytes",
                "quality/releases.json": "frozen-release-bytes",
            }
            for name, value in contents.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8")
            result = archive.run(root)
            self.assertEqual(2, result["confirmed_social_links"])
            for name in ("episodes/tt-006.json", "quality/releases.json", "site/media/tt-006.mp4"):
                self.assertEqual(contents[name], (root / name).read_text(encoding="utf-8"))
            self.assertEqual(0, archive.run(root)["changed_pages"])
            data = json.loads((root / "site/papers.json").read_text(encoding="utf-8"))
            self.assertEqual(2, len(data[0]["confirmed_publications"]))


if __name__ == "__main__":
    unittest.main()
