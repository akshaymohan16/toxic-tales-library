#!/usr/bin/env python3
"""Toxic Tales fail-closed repository readiness watchdog.

No Metricool credentials are stored in GitHub. This checks the ledger's
authenticated-provider receipts, not the real-time provider state. The existing
ChatGPT daily publisher must independently fetch Metricool and update records.
"""
import argparse
import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Vienna")
SLOTS = (("tuesday", 1, "REEL"), ("thursday", 3, "CAROUSEL"),
         ("saturday", 5, "REEL"))
FINAL = {"scheduled", "published"}
RESERVED = {"scheduled", "published", "draft_held_for_quality_review"}
GRACE = timedelta(hours=3)
HEARTBEAT_MAX_AGE = timedelta(hours=42)


def read(root, rel, default=None):
    file = root / rel
    return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else default


def local_date(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("Missing timestamp timezone: " + value)
    return dt.astimezone(ZONE)


def target_week(now):
    local = now.astimezone(ZONE)
    if local.weekday() == 6:
        return None  # Sunday production in progress: Monday is the hard deadline
    return local.date() - timedelta(days=local.weekday())


def release_check(root, receipt, releases, errors):
    pid = receipt["post_id"]
    episode_id = receipt.get("episode_id", "")
    file = root / "episodes" / (episode_id.lower() + ".json")
    if not file.is_file():
        errors.append(pid + ": missing source episode")
        return
    ep = json.loads(file.read_text(encoding="utf-8"))
    if ep.get("id") != episode_id or ep.get("doi") != receipt.get("doi"):
        errors.append(pid + ": episode DOI mismatch")
    evidence = ep.get("evidence_file", "")
    if not evidence or not (root / evidence).is_file():
        errors.append(pid + ": original-paper evidence file missing")
    release = releases.get(episode_id, {})
    if release.get("decision") != "release":
        errors.append(pid + ": no final quality release")
        return
    if receipt.get("release_fingerprint") != release.get("fingerprint"):
        errors.append(pid + ": final media fingerprint does not match release")
    files = receipt.get("source_files_sha256")
    if not isinstance(files, dict) or not files:
        errors.append(pid + ": media SHA-256 receipt missing")
    else:
        signed = release.get("files", {})
        for name, digest in files.items():
            if signed.get(name) != digest:
                errors.append(pid + ": exact media hash mismatch: " + name)
    if (receipt.get("format") == "REEL" and
            ep.get("production", {}).get("renderer") == "nature-branded-9"):
        if (release.get("final_editorial_review", {}).get("decision") != "pass"
                or release.get("branding_review", {}).get("decision") != "pass"):
            errors.append(pid + ": future film lacks final editorial/brand review")


def audit(root, now):
    if now.tzinfo is None:
        raise ValueError("Watchdog time must have timezone")
    now = now.astimezone(ZONE)
    errors, warnings, rows = [], [], []
    config = read(root, "automation/config.json", {})
    ledger = read(root, "automation/published.json", {"posts": []})
    releases = read(root, "quality/releases.json", {})
    publisher = read(root, "automation/publisher-status.json", {})
    if config.get("allowed_repository") != "akshaymohan16/toxic-tales-library":
        errors.append("Repository boundary mismatch")
    if config.get("metricool_brand_id") != "7937614":
        errors.append("Unexpected Metricool brand")
    if config.get("timezone") != "Europe/Vienna":
        errors.append("Incorrect time zone")
    if config.get("publishing_paused") is not False:
        errors.append("Publishing is paused")
    posts = ledger.get("posts", [])
    if not isinstance(posts, list):
        posts = []
        errors.append("Publication ledger is not a list")
    ids, uuids, reel_dois = set(), set(), set()
    count = 0
    for p in posts:
        pid = p.get("post_id")
        if not pid or pid in ids:
            errors.append("Duplicate or missing post ID: " + str(pid))
        ids.add(pid)
        status = p.get("status")
        if status in FINAL:
            uuid = p.get("metricool_uuid")
            if not uuid or uuid in uuids:
                errors.append("Duplicate or missing active provider UUID: " + str(uuid))
            uuids.add(uuid)
            if p.get("format") == "REEL":
                doi = p.get("doi")
                if not doi or doi in reel_dois:
                    errors.append("Duplicate DOI+REEL across all posts: " + str(doi))
                reel_dois.add(doi)
        if status in RESERVED:
            try:
                date = local_date(p["publication_date"])
                if date.year == now.year and date.month == now.month:
                    count += 1
            except (KeyError, ValueError, TypeError):
                errors.append("Missing or invalid publication date: " + str(pid))
    limit = config.get("monthly_publication_cap", 20)
    if count > limit:
        errors.append("Monthly conservative post reservations exceed free plan cap")
    if count > 18:
        warnings.append("Only two or fewer calendar reservations remain")

    heartbeat = publisher.get("updated_at")
    if not heartbeat:
        errors.append("Daily publisher heartbeat missing")
    else:
        try:
            age = now - local_date(heartbeat)
            if age > HEARTBEAT_MAX_AGE:
                errors.append("Publisher heartbeat stale by " +
                              str(round(age.total_seconds() / 3600, 1)) + "h")
            if age < -timedelta(minutes=15):
                errors.append("Publisher heartbeat timestamp in future")
        except (ValueError, TypeError):
            errors.append("Invalid publisher heartbeat timestamp")

    monday = target_week(now)
    if monday is None:
        warnings.append("Sunday producer window; Monday check is the readiness deadline")
    else:
        for label, day_offset, fmt in SLOTS:
            due = datetime.combine(monday + timedelta(days=day_offset),
                                   time(10), tzinfo=ZONE)
            matching = []
            for p in posts:
                if p.get("status") not in FINAL or p.get("format") != fmt:
                    continue
                try:
                    if local_date(p["publication_date"]) == due:
                        matching.append(p)
                except (KeyError, ValueError, TypeError):
                    continue
            row = {"slot": label, "due": due.isoformat(),
                   "post_id": matching[0].get("post_id") if len(matching) == 1 else None}
            rows.append(row)
            if len(matching) != 1:
                errors.append(label + ": expected exactly one active " + fmt +
                              " at " + due.isoformat() + ", found " + str(len(matching)))
                continue
            p = matching[0]
            row["status"] = p["status"]
            if p.get("auto_publish") is not True or p.get("draft") is not False:
                errors.append(p["post_id"] + ": not autoPublish non-draft")
            if not p.get("metricool_uuid") or not p.get("planner_url"):
                errors.append(p["post_id"] + ": provider reservation receipt missing")
            if p["status"] == "scheduled" and now - due >= GRACE:
                errors.append(p["post_id"] + ": overdue after 3h; positive "
                              "Instagram publication receipt still missing")
            if p["status"] == "published":
                if p.get("provider_status") != "PUBLISHED" or not p.get("public_url"):
                    errors.append(p["post_id"] + ": missing PUBLISHED status/live URL")
            release_check(root, p, releases, errors)
            if fmt == "CAROUSEL":
                if not any(q.get("format") == "REEL" and
                           q.get("doi") == p.get("doi") and
                           q.get("status") in FINAL for q in posts):
                    errors.append(p["post_id"] + ": companion Reel not found")

    report = {"ok": not errors, "checked_at": now.isoformat(),
              "week_start": monday.isoformat() if monday else None,
              "basis": "committed ledger receipts, NOT live Metricool availability",
              "reserved_month": count, "limit": limit,
              "slots": rows, "errors": errors, "warnings": warnings}
    return report


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--root", default=".")
    arg.add_argument("--now", default=None)
    args = arg.parse_args()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    report = audit(Path(args.root), now)
    print(json.dumps(report, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as file:
            file.write("## Toxic Tales readiness watchdog\n\n")
            file.write("**" + ("PASS" if report["ok"] else "FAIL") + "** " +
                       report["checked_at"] + " (Europe/Vienna)\n\n")
            file.write("Repository receipts only; existing daily publisher must "
                       "verify the actual Metricool calendar.\n\n")
            for row in report["slots"]:
                file.write("- " + row["slot"] + ": " + str(row["post_id"]) + "\n")
            for error in report["errors"]:
                file.write("- **FAIL:** " + error + "\n")
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
