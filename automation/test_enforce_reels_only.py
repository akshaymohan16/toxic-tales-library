import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from enforce_reels_only import (authorized_one_off_slot, local_slot, run, sanitize_queue,
                                validate_config, validate_episode, validate_one_off_slots)


FIRST = local_slot("2026-11-17T10:00:00+01:00")
NOW = datetime.fromisoformat("2026-11-13T12:00:00+01:00")
CONFIG = {"slots": {"tuesday": "REEL", "friday": "REEL"},
          "target_weekly_posts": {"reels": 2, "carousel": 0},
          "target_weekly_destination_posts": {"instagram": 2, "youtube": 2, "total": 4},
          "first_reels_only_publication": FIRST.isoformat()}
ONE_OFF_DATE = "2026-11-13T18:00:00+01:00"


def one_off_config():
    result = copy.deepcopy(CONFIG)
    result["owner_authorized_one_off_slots"] = [
        {"episode_id": "TT-008", "post_id": "TT-008" + suffix, "platform": network,
         "format": fmt, "publication_date": ONE_OFF_DATE,
         "authorized_at": "2026-11-13T13:20:50+01:00",
         "reason": "Owner explicitly requested a new Reel today; Tuesday bumblebee unchanged"}
        for network, fmt, suffix in (("instagram", "REEL", "-REEL"),
                                     ("youtube", "SHORT", "-YOUTUBE-SHORT"))]
    return result


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


class OwnerAuthorizedOneOffTests(unittest.TestCase):
    def test_exact_authorized_video_passes_source_and_queue_before_due(self):
        config = one_off_config()
        post = candidate(publication_date=ONE_OFF_DATE)
        episode = {"id": "TT-008", "production": {"renderer": "nature-motion-10"}, "posts": [post]}
        self.assertEqual(validate_config(config), FIRST)
        validate_episode(episode, FIRST, config)
        kept, removed = sanitize_queue([post], {"posts": []}, FIRST, NOW, config)
        self.assertEqual(kept, [post])
        self.assertEqual(removed, [])
        short = {**post, "id": "TT-008-YOUTUBE-SHORT", "platform": "youtube", "format": "SHORT"}
        self.assertEqual(authorized_one_off_slot(short, config).isoformat(), ONE_OFF_DATE)

    def test_absent_authorization_and_non_exact_identity_fail_closed(self):
        base = candidate(publication_date=ONE_OFF_DATE)
        self.assertIsNone(authorized_one_off_slot(base))
        self.assertEqual(sanitize_queue([base], {"posts": []}, FIRST, NOW)[0], [])
        for changes in ({"episode_id": "TT-009"}, {"id": "TT-009-REEL"},
                        {"platform": "youtube"}, {"format": "CAROUSEL"},
                        {"publication_date": "2026-11-13T18:01:00+01:00"},
                        {"publication_date": "2026-11-20T18:00:00+01:00"}):
            with self.subTest(changes=changes):
                post = {**base, **changes}
                self.assertIsNone(authorized_one_off_slot(post, one_off_config()))
                self.assertEqual(sanitize_queue([post], {"posts": []}, FIRST, NOW, one_off_config())[0], [])

    def test_exception_does_not_bypass_release_receipt_duplicate_or_past_guards(self):
        config, post = one_off_config(), candidate(publication_date=ONE_OFF_DATE)
        for changes in ({"quality_released": False}, {"scientifically_reviewed": False}):
            self.assertEqual(sanitize_queue([{**post, **changes}], {"posts": []}, FIRST, NOW, config)[0], [])
        for receipt in ({"status": "scheduled"}, {"status": "submission_uncertain"},
                        {"status": "ready", "metricool_uuid": "existing"},
                        {"status": "ready", "metricool_id": "existing"},
                        {"status": "ready", "publication_eligible": False}):
            self.assertEqual(sanitize_queue([post], {"posts": [{"post_id": post["id"], **receipt}]},
                                            FIRST, NOW, config)[0], [])
        self.assertEqual(len(sanitize_queue([post, post], {"posts": []}, FIRST, NOW, config)[0]), 1)
        for instant in (ONE_OFF_DATE, "2026-11-13T18:00:01+01:00"):
            self.assertEqual(sanitize_queue([post], {"posts": []}, FIRST,
                                            datetime.fromisoformat(instant), config)[0], [])

    def test_malformed_incomplete_or_historical_authorization_is_rejected(self):
        malformed = []
        for value in (None, {}, "2026-11-13", ["invalid"]):
            malformed.append({**CONFIG, "owner_authorized_one_off_slots": value})
        for field, value in (("episode_id", "TT-003"), ("platform", "tiktok"),
                             ("post_id", "TT-999-REEL"), ("format", "CAROUSEL"),
                             ("publication_date", "2026-11-13T18:00:00"),
                             ("authorized_at", ONE_OFF_DATE), ("reason", "")):
            config = one_off_config()
            config["owner_authorized_one_off_slots"][0][field] = value
            malformed.append(config)
        config = one_off_config()
        config["owner_authorized_one_off_slots"].pop()
        malformed.append(config)
        config = one_off_config()
        config["owner_authorized_one_off_slots"].append(config["owner_authorized_one_off_slots"][0])
        malformed.append(config)
        for config in malformed:
            with self.subTest(records=config.get("owner_authorized_one_off_slots")):
                with self.assertRaises(ValueError):
                    validate_one_off_slots(config)
                with self.assertRaises(ValueError):
                    sanitize_queue([candidate(publication_date=ONE_OFF_DATE)], {"posts": []}, FIRST, NOW, config)


if __name__ == "__main__":
    unittest.main()
