#!/usr/bin/env python3
"""Apply current cadence without editing hash-bound legacy render inputs.

This is an additional policy gate, not a release approval or provider client.
Research archives and frozen historical sources remain unchanged.
"""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ZONE = ZoneInfo("Europe/Vienna")
FROZEN_EPISODES = frozenset(f"TT-{i:03}" for i in range(1, 8))
RETIRED_EPISODES = frozenset({"TT-003"})
UNSUBMITTED_STATES = frozenset({"ready", "released", "approved", "unscheduled"})


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def local_slot(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timezone required")
        result = result.astimezone(ZONE)
        if result.weekday() not in (1, 4) or (result.hour, result.minute, result.second, result.microsecond) != (10, 0, 0, 0):
            raise ValueError("requires Tuesday or Friday 10:00 Europe/Vienna")
        return result
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid publication slot {value!r}: {error}") from error


def validate_config(config):
    if config.get("slots") != {"tuesday": "REEL", "friday": "REEL"}:
        raise ValueError("Current source policy requires Tuesday/Friday Reels only")
    if config.get("target_weekly_posts") != {"reels": 2, "carousel": 0}:
        raise ValueError("Current production policy requires two Reels and zero carousels")
    if config.get("target_weekly_destination_posts") != {"instagram": 2, "youtube": 2, "total": 4}:
        raise ValueError("Both weekly videos require Instagram and YouTube destinations")
    return local_slot(config["first_reels_only_publication"])


def validate_episode(episode, first_slot):
    if episode.get("id") in FROZEN_EPISODES:
        return
    if not episode.get("production"):
        return
    if episode.get("slides"):
        raise ValueError(f"{episode.get('id')}: new carousel slide production is disabled")
    for post in episode.get("posts", []):
        if post.get("format") != "REEL":
            raise ValueError(f"{episode.get('id')}: new source posts must be Reels")
        if local_slot(post.get("publication_date")) < first_slot:
            raise ValueError(f"{episode.get('id')}: historical backfill is disabled")


def sanitize_queue(queue, ledger, first_slot, now):
    receipts = {post["post_id"]: post for post in ledger.get("posts", [])}
    kept, removed, seen = [], [], set()
    for original in queue:
        item = copy.deepcopy(original)
        post_id = item.get("id")
        receipt = receipts.get(post_id)
        reason = None
        if item.get("format") != "REEL":
            reason = "non-Reel format disabled"
        elif item.get("episode_id") in RETIRED_EPISODES:
            reason = "owner-rejected episode remains retired"
        elif receipt and (receipt.get("status") not in UNSUBMITTED_STATES
                          or receipt.get("metricool_uuid") or receipt.get("metricool_id")
                          or receipt.get("publication_eligible") is False):
            reason = "existing receipt requires provider reconciliation, not a new submission"
        elif not item.get("quality_released") or not item.get("scientifically_reviewed"):
            reason = "existing release and science gates not passed"
        elif not post_id or post_id in seen:
            reason = "missing or duplicate post identity"
        else:
            # Ledger may record an authorized changed date for an unsent item.
            if receipt and receipt.get("publication_date"):
                item["publication_date"] = receipt["publication_date"]
            try:
                due = local_slot(item.get("publication_date"))
                if due < first_slot or due <= now.astimezone(ZONE):
                    reason = "past publication/backfill disabled"
            except ValueError as error:
                reason = str(error)
        if reason:
            removed.append({"post_id": post_id, "reason": reason})
        else:
            seen.add(post_id)
            kept.append(item)
    return kept, removed


def run(root, sanitize=False, now=None):
    config = read(root / "automation/config.json")
    first_slot = validate_config(config)
    for path in sorted((root / "episodes").glob("*.json")):
        validate_episode(read(path), first_slot)
    if not sanitize:
        return {"decision": "pass", "scope": "new source cadence; legacy sources untouched"}
    now = now or datetime.now(timezone.utc)
    queue_path = root / "site/publish-queue.json"
    queue, removed = sanitize_queue(read(queue_path), read(root / "automation/published.json"), first_slot, now)
    write(queue_path, queue)
    health_path = root / "site/health.json"
    if health_path.exists():
        health = read(health_path)
        health["queue_count"] = len(queue)
        write(health_path, health)
    result = {"decision": "pass", "checked_at": now.isoformat(), "queue_count": len(queue), "removed": removed,
              "note": "Policy filtering only; no release approval, scheduling or publication performed."}
    write(root / "site/qa/reels-only-policy.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--sanitize-queue", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.sanitize_queue), indent=2))
