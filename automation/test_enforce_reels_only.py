import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from enforce_reels_only import local_slot, run, sanitize_queue, validate_config, validate_episode


FIRST = local_slot("2026-11-17T10:00:00+01:00")
NOW = datetime.fromisoformat("2026-11-13T12:00:00+01:00")
CONFIG = {"slots": {"tuesday": "REEL", "friday": "REEL"},
          "target_weekly_posts": {"reels": 2, "carousel": 0},
          "target_weekly_destination_posts": {"instagram": 2, "youtube": 2, "total": 4},
          "first_reels_only_publication": FIRST.isoformat()}


def candidate(post_id="TT-008-REEL", **extra):
    return {"id": post_id, "episode_id": post_id[:6], "format": "REEL",
            "publication_date": "2026-11-20T10:00:00+01:00", "quality_released": True,
            "scientifically_reviewed": True, **extra}


class ReelsPolicyTest(unittest.TestCase):
    def test_new_carousel_source_is_rejected_but_historical_source_unchanged(self):
        episode = {"id": "TT-008", "production": {"renderer": "nature-motion-10"},
                   "slides": ["new page"], "posts": []}
        with self.assertRaises(ValueError):
            validate_episode(episode, FIRST)
        episode["id"] = "TT-005"
        before = copy.deepcopy(episode)
        validate_episode(episode, FIRST)
        self.assertEqual(episode, before)

    def test_new_carousel_post_and_wrong_cadence_fail(self):
        episode = {"id": "TT-008", "production": {"renderer": "nature-motion-10"}, "posts": [candidate(format="CAROUSEL")]}
        with self.assertRaises(ValueError):
            validate_episode(episode, FIRST)
        episode["posts"] = [candidate(publication_date="2026-11-21T10:00:00+01:00")]
        with self.assertRaises(ValueError):
            validate_episode(episode, FIRST)

    def test_slot_uses_vienna_dst_and_rejects_naive_or_wrong_time(self):
        self.assertEqual(local_slot("2027-07-02T08:00:00Z").hour, 10)
        self.assertEqual(local_slot("2026-11-20T09:00:00Z").hour, 10)
        for value in ("2026-11-20T10:00:00", "2026-11-20T09:00:00+01:00", "2026-11-19T10:00:00+01:00"):
            with self.assertRaises(ValueError):
                local_slot(value)

    def test_held_retired_published_scheduled_and_uncertain_items_never_reenter_queue(self):
        for status in ("draft_held_for_quality_review", "retired", "published", "scheduled", "submission_uncertain", "failed_retry_pending"):
            with self.subTest(status=status):
                result, removed = sanitize_queue([candidate()], {"posts": [{"post_id": "TT-008-REEL", "status": status}]}, FIRST, NOW)
                self.assertEqual(result, [])
                self.assertEqual(len(removed), 1)

    def test_owner_rejected_episode_and_carousels_never_reenter_queue_without_ledger(self):
        result, _ = sanitize_queue([candidate("TT-003-REEL"), candidate(format="CAROUSEL")], {"posts": []}, FIRST, NOW)
        self.assertEqual(result, [])

    def test_existing_provider_identity_blocks_even_unscheduled_status(self):
        for field in ("metricool_id", "metricool_uuid"):
            receipt = {"post_id": "TT-008-REEL", "status": "ready", field: "123"}
            self.assertEqual(sanitize_queue([candidate()], {"posts": [receipt]}, FIRST, NOW)[0], [])

    def test_past_bad_cadence_and_unreleased_candidates_removed(self):
        bad = [candidate(publication_date="2026-11-10T10:00:00+01:00"),
               candidate(publication_date="2026-11-21T10:00:00+01:00"),
               candidate(quality_released=False), candidate(scientifically_reviewed=False)]
        self.assertEqual(sanitize_queue(bad, {"posts": []}, FIRST, NOW)[0], [])

    def test_released_future_video_preserved_and_ledger_unsent_date_used(self):
        item = candidate()
        receipt = {"post_id": item["id"], "status": "ready", "publication_date": FIRST.isoformat()}
        result, removed = sanitize_queue([item, item], {"posts": [receipt]}, FIRST, NOW)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["publication_date"], FIRST.isoformat())
        self.assertEqual(len(removed), 1)
        self.assertEqual(item["publication_date"], "2026-11-20T10:00:00+01:00")

    def test_wrong_config_cannot_silently_enable_old_slots(self):
        invalid = copy.deepcopy(CONFIG)
        invalid["slots"]["thursday"] = "CAROUSEL"
        with self.assertRaises(ValueError):
            validate_config(invalid)

    def test_file_gate_updates_queue_count_without_altering_source_or_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = {"automation/config.json": CONFIG, "automation/published.json": {"posts": []},
                        "episodes/tt-005.json": {"id": "TT-005", "slides": ["historic"]},
                        "site/papers.json": [{"id": "TT-005", "historic": True}],
                        "site/health.json": {"queue_count": 2, "commit": "abc"},
                        "site/publish-queue.json": [candidate(), candidate(format="CAROUSEL")]}
            for name, value in fixtures.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(value), encoding="utf-8")
            before = (root / "episodes/tt-005.json").read_bytes(), (root / "site/papers.json").read_bytes()
            result = run(root, sanitize=True, now=NOW)
            self.assertEqual(result["queue_count"], 1)
            self.assertEqual(json.loads((root / "site/health.json").read_text())["queue_count"], 1)
            self.assertEqual(before, ((root / "episodes/tt-005.json").read_bytes(), (root / "site/papers.json").read_bytes()))


if __name__ == "__main__":
    unittest.main()
