#!/usr/bin/env python3
"""Toxic Tales fail-closed repository readiness watchdog.

No Metricool credentials are stored in GitHub. This checks the ledger's
authenticated-provider receipts, not the real-time provider state. The existing
ChatGPT daily publisher must independently fetch Metricool and update records.
"""
import argparse
import copy
import hashlib
import json
import os
from calendar import monthrange
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Vienna")
SLOTS = (("tuesday", 1, "REEL"), ("thursday", 3, "CAROUSEL"),
         ("saturday", 5, "REEL"))
FINAL = {"scheduled", "published"}
RESERVED = {"scheduled", "published", "draft_held_for_quality_review"}
RESERVED |= {"submission_uncertain", "pending_confirmation", "failed_retry_pending"}
GRACE = timedelta(hours=3)
HEARTBEAT_MAX_AGE = timedelta(hours=42)
YOUTUBE_CHANNEL = "UCDvftxMMdtGSntm-ezcPfCg"


def read(root, rel, default=None):
    file = root / rel
    return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else default


def local_date(value):
    # Provider timestamps use ISO 8601 Z; Python before 3.11 needs +00:00.
    dt = datetime.fromisoformat(value[:-1] + "+00:00" if isinstance(value, str)
                                and value.endswith("Z") else value)
    if dt.tzinfo is None:
        raise ValueError("Missing timestamp timezone: " + value)
    return dt.astimezone(ZONE)


def target_week(now):
    local = now.astimezone(ZONE)
    if local.weekday() == 6:
        return None  # Sunday production in progress: Monday is the hard deadline
    return local.date() - timedelta(days=local.weekday())


def platform(post):
    """Historical receipts predate the platform field and are Instagram only."""
    return post.get("platform", "instagram")


def video_files(post):
    files = post.get("source_files_sha256", {})
    if not isinstance(files, dict):
        return {}
    return {name: digest for name, digest in
            files.items() if isinstance(name, str) and
            name.lower().endswith((".mp4", ".mov"))}


def destination_key(post):
    return platform(post) + ":" + str(post.get("post_id", ""))


def metadata_digest(post):
    meta = post.get("youtube", {})
    canonical = {key: meta.get(key) for key in
                 ("title", "description", "made_for_kids", "privacy", "is_ai_generated",
                  "source_video_sha256")}
    canonical["channel_id"] = post.get("youtube_channel_id")
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def valid_public_url(url, network):
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        if network == "instagram":
            return parsed.hostname in {"instagram.com", "www.instagram.com"} and (
                parsed.path.startswith("/reel/") or parsed.path.startswith("/p/"))
        if parsed.hostname == "youtu.be":
            return len(parsed.path.strip("/")) == 11
        if parsed.hostname in {"youtube.com", "www.youtube.com"}:
            return ((parsed.path.startswith("/shorts/") and
                     len(parsed.path.removeprefix("/shorts/").strip("/")) == 11)
                    or (parsed.path == "/watch" and
                        len(parse_qs(parsed.query).get("v", [""])[0]) == 11))
    except (TypeError, ValueError, AttributeError):
        pass
    return False


def month_budget(posts, now, year, month, observed_used=0, observed_published_keys=None):
    """Count each destination once and protect unscheduled remaining IG slots.

    The provider counter already includes its saved published-ID baseline. Add
    only publications outside that baseline, retaining the full ledger as floor.
    Future IG dates without receipts are reservations too, so an early YouTube
    submission cannot exhaust the month's Instagram capacity.
    """
    published = pending = 0
    published_keys = set()
    occupied_ig = set()
    for post in posts:
        if post.get("status") not in RESERVED:
            continue
        try:
            due = local_date(post["publication_date"])
        except (KeyError, TypeError, ValueError):
            continue
        if (due.year, due.month) != (year, month):
            continue
        if post.get("status") == "published":
            published += 1
            published_keys.add(destination_key(post))
        else:
            pending += 1
        if platform(post) == "instagram" and post.get("status") in FINAL:
            occupied_ig.add((due, post.get("format")))
    unfilled_ig = 0
    for day in range(1, monthrange(year, month)[1] + 1):
        due = datetime(year, month, day, 10, tzinfo=ZONE)
        fmt = {1: "REEL", 3: "CAROUSEL", 5: "REEL"}.get(due.weekday())
        if fmt and due > now and (due, fmt) not in occupied_ig:
            unfilled_ig += 1
    since_observation = (len(published_keys - set(observed_published_keys))
                         if observed_published_keys is not None else 0)
    used = max(observed_used + since_observation, published)
    return {"month": f"{year:04d}-{month:02d}", "published_used": used,
            "pending_destination_reservations": pending,
            "unfilled_instagram_reservations": unfilled_ig,
            "projected": used + pending + unfilled_ig}


def publication_check(post, due, now, errors):
    pid = post.get("post_id", "unknown")
    network = platform(post)
    if post.get("auto_publish") is not True or post.get("draft") is not False:
        errors.append(pid + ": not autoPublish non-draft")
    if not all(post.get(key) for key in ("metricool_id", "metricool_uuid", "planner_url")):
        errors.append(pid + ": provider reservation receipt missing")
    if post["status"] == "scheduled":
        if post.get("provider_status") not in {"PENDING", "PUBLISHING", "PROCESSING"}:
            errors.append(pid + ": scheduled receipt has invalid provider status")
        if now - due >= GRACE:
            errors.append(pid + ": overdue after 3h; positive " + network +
                          " publication receipt still missing")
    if post["status"] == "published":
        if (post.get("provider_status") != "PUBLISHED" or
                not valid_public_url(post.get("public_url"), network)):
            errors.append(pid + ": missing PUBLISHED status/live URL")
        if network == "youtube":
            live = post.get("live_verification", {})
            if (live.get("decision") != "pass" or
                    live.get("url") != post.get("public_url") or
                    live.get("channel_id") != YOUTUBE_CHANNEL):
                errors.append(pid + ": YouTube live video/channel verification missing")
            try:
                checked = local_date(live["checked_at"])
                if checked < due or checked > now + timedelta(minutes=15):
                    raise ValueError("Invalid live verification date")
            except (KeyError, ValueError, TypeError):
                errors.append(pid + ": invalid YouTube live verification timestamp")


def youtube_check(root, post, posts, releases, now, errors):
    pid = post.get("post_id", "unknown")
    if post.get("format") != "SHORT" or post.get("youtube_channel_id") != YOUTUBE_CHANNEL:
        errors.append(pid + ": incorrect YouTube format/channel")
    try:
        due = local_date(post["publication_date"])
        if due.weekday() != 1 or (due.hour, due.minute, due.second) != (10, 0, 0):
            errors.append(pid + ": YouTube must use the Tuesday 10:00 slot")
        publication_check(post, due, now, errors)
    except (KeyError, ValueError, TypeError):
        errors.append(pid + ": invalid YouTube publication date")
        return
    sources = [p for p in posts if platform(p) == "instagram" and
               p.get("post_id") == post.get("source_post_id") and
               p.get("status") in FINAL and p.get("format") == "REEL"]
    if len(sources) != 1:
        errors.append(pid + ": one approved source Instagram Reel is required")
    else:
        source = sources[0]
        try:
            same_date = local_date(source["publication_date"]) == due
        except (KeyError, ValueError, TypeError):
            same_date = False
        if (source.get("episode_id") != post.get("episode_id") or
                source.get("doi") != post.get("doi") or
                source.get("release_fingerprint") != post.get("release_fingerprint") or
                video_files(source) != video_files(post) or not video_files(post) or
                not same_date):
            errors.append(pid + ": YouTube source Reel/date/media identity mismatch")
    meta = post.get("youtube", {})
    title, description = meta.get("title", ""), meta.get("description", "")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
        errors.append(pid + ": invalid YouTube title")
    if (not isinstance(description, str) or not 1 <= len(description.strip()) <= 5000 or
            not post.get("doi") or post.get("doi") not in description or
            "https://akshaymohan16.github.io/toxic-tales-library/sources/" not in description):
        errors.append(pid + ": YouTube description/citation/research link missing")
    if meta.get("made_for_kids") is not False or meta.get("privacy") != "PUBLIC":
        errors.append(pid + ": YouTube audience/privacy incorrect")
    if meta.get("is_ai_generated") is not True:
        errors.append(pid + ": YouTube synthetic-media disclosure missing")
    if (meta.get("review_decision") != "pass" or
            meta.get("rights_review_decision") != "pass" or
            meta.get("reviewed_release_fingerprint") != post.get("release_fingerprint") or
            meta.get("source_video_sha256") not in video_files(post).values()):
        errors.append(pid + ": exact-media YouTube metadata/rights review missing")
    if meta.get("metadata_sha256") != metadata_digest(post):
        errors.append(pid + ": YouTube metadata changed since its review")

    provider = post.get("provider_readback", {})
    settings = provider.get("youtubeData", {})
    destinations = provider.get("providers", [])
    youtube_receipts = [p for p in destinations if p.get("network") == "youtube"]
    media = post.get("metricool_media_urls", [])
    hashes = post.get("metricool_media_sha256", {})
    if (post.get("schedule_readback_verified") is not True or
            str(provider.get("id")) != str(post.get("metricool_id")) or
            str(provider.get("uuid")) != str(post.get("metricool_uuid")) or
            provider.get("text") != description or settings.get("title") != title or
            settings.get("madeForKids") is not False or
            settings.get("isAiGeneratedContent") is not True or
            str(settings.get("privacy", "")).upper() != "PUBLIC" or
            str(settings.get("type", "")).upper() not in {"SHORT", "SHORTS"} or
            provider.get("autoPublish") is not True or provider.get("draft") is not False or
            len(destinations) != 1 or len(youtube_receipts) != 1 or
            youtube_receipts[0].get("status") != post.get("provider_status") or
            not isinstance(media, list) or len(media) != 1 or provider.get("media") != media):
        errors.append(pid + ": YouTube provider readback does not match reviewed schedule/settings/media")
    if (post.get("status") == "published" and len(youtube_receipts) == 1 and
            youtube_receipts[0].get("publicUrl") != post.get("public_url")):
        errors.append(pid + ": published YouTube URL differs from provider receipt")
    if (not isinstance(hashes, dict) or not media or
            any(hashes.get(url) != meta.get("source_video_sha256") for url in media)):
        errors.append(pid + ": hosted YouTube media hash verification missing")
    try:
        stamp = provider["publicationDate"]
        provider_due = datetime.fromisoformat(stamp["dateTime"])
        if provider_due.tzinfo is None:
            provider_due = provider_due.replace(tzinfo=ZoneInfo(stamp["timezone"]))
        checked = local_date(post["provider_readback_checked_at"])
        if provider_due.astimezone(ZONE) != due or checked > now + timedelta(minutes=15):
            raise ValueError("Readback timestamp/date mismatch")
    except (KeyError, ValueError, TypeError):
        errors.append(pid + ": invalid YouTube provider readback date/timestamp")
    release_check(root, post, releases, errors)


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
    if (receipt.get("format") in {"REEL", "SHORT"} and
            ep.get("production", {}).get("renderer") in {"nature-branded-9", "nature-motion-10"}):
        if (release.get("final_editorial_review", {}).get("decision") != "pass"
                or release.get("branding_review", {}).get("decision") != "pass"):
            errors.append(pid + ": future film lacks final editorial/brand review")
        if ep["production"]["renderer"] == "nature-motion-10":
            if not motion_release_identity_ok(root, ep, release):
                errors.append(pid + ": motion film lacks current independent exact-file reviews")


def motion_release_identity_ok(root, episode, release):
    """Read-only, stdlib-only receipt check; the build remains the render gate.

    Match the canonical source and motion identities used by editorial_gate and
    motion_spec without importing image, neural voice or rendering dependencies
    into the lightweight watchdog. These records do not prove visual quality.
    """
    def digest(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    placeholders = {"", "pass", "passed", "checked", "ok", "okay", "yes", "tbd",
                    "todo", "n/a", "none", "placeholder"}
    def text(value):
        return isinstance(value, str) and value.strip().lower() not in placeholders

    try:
        evidence_path = (root / episode["evidence_file"]).resolve()
        if not evidence_path.is_relative_to((root / "evidence").resolve()):
            return False
        evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        if release.get("evidence_sha256") != evidence_sha:
            return False
        production = episode["production"]
        if production.get("motion", {}).get("evidence_sha256") != evidence_sha:
            return False
        source = copy.deepcopy(episode)
        source.pop("editorial_review", None)
        source_sha = digest({"standard": "story-first-v1", "episode": source,
                             "evidence_text": evidence_path.read_text(encoding="utf-8")})
        spec_sha = digest({"standard": "toxic-tales-motion-v1", "doi": episode["doi"],
                           "production": production})
        author = episode.get("script_author", production.get("script_author", "Toxic Tales production editor"))
        for field, standard in (("final_editorial_review", "story-first-v1"),
                                ("branding_review", "toxic-tales-branding-v1"),
                                ("motion_review", "toxic-tales-motion-v1")):
            review = release.get(field, {})
            if (review.get("decision") != "pass" or review.get("standard") != standard
                    or review.get("independent_from_script_author") is not True
                    or review.get("reviewer") == author
                    or not all(text(review.get(k)) for k in ("reviewer", "reviewed_at"))
                    or review.get("reviewed_encoded_frames") is not True):
                return False
            if any(not release.get(k) or review.get(k) != release[k]
                   for k in ("fingerprint", "files", "evidence_sha256")):
                return False
        if release["final_editorial_review"].get("source_sha256") != source_sha:
            return False
        branding = release["branding_review"]
        logo = read(root, "assets/branding/toxic-tales-logo.json", {})
        if not logo.get("sha256") or branding.get("logo_sha256") != logo["sha256"]:
            return False
        if not all(branding.get(k) is True for k in ("reviewed_opening_frames",
                "reviewed_every_shot_and_transition", "reviewed_final_frame",
                "reviewed_cover", "reviewed_phone_scale")):
            return False
        motion = release["motion_review"]
        if (motion.get("source_sha256") != source_sha or motion.get("motion_spec_sha256") != spec_sha
                or motion.get("reviewed_every_shot_and_transition") is not True
                or motion.get("reviewed_phone_scale") is not True):
            return False
        for key in ("kinetic_text", "transitions", "ecological_motion", "camera_motion",
                    "evidence_bound_data", "caption_sync"):
            check = motion.get("checks", {}).get(key, {})
            if (check.get("decision") != "pass" or not text(check.get("finding"))
                    or not text(check.get("basis"))):
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


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
    youtube = config.get("youtube", {})
    youtube_enabled = youtube.get("enabled") is True
    if youtube_enabled and (youtube.get("channel_id") != YOUTUBE_CHANNEL or
                            youtube.get("weekly_shorts") != 1 or
                            youtube.get("source_slot") != "tuesday" or
                            youtube.get("made_for_kids") is not False or
                            youtube.get("privacy") != "PUBLIC"):
        errors.append("YouTube routing, channel, audience or privacy configuration mismatch")
    ids, uuids, reel_dois, video_hashes, youtube_weeks = set(), set(), set(), set(), set()
    count = 0
    for p in posts:
        pid = p.get("post_id")
        if not pid or pid in ids:
            errors.append("Duplicate or missing post ID: " + str(pid))
        ids.add(pid)
        network = platform(p)
        if network not in {"instagram", "youtube"}:
            errors.append("Unsupported publication platform: " + str(network))
        status = p.get("status")
        if status in RESERVED and network == "youtube":
            try:
                week = local_date(p["publication_date"]).date().isocalendar()[:2]
                if week in youtube_weeks:
                    errors.append("More than one YouTube destination reserved in ISO week " + str(week))
                youtube_weeks.add(week)
            except (KeyError, ValueError, TypeError):
                errors.append(str(pid) + ": invalid reserved YouTube date")
        if status in FINAL:
            if p.get("episode_id") == "TT-003":
                errors.append("Rejected TT-003 must never be an active publication")
            uuid = p.get("metricool_uuid")
            if not uuid or (network, uuid) in uuids:
                errors.append("Duplicate or missing active provider UUID: " + str(uuid))
            uuids.add((network, uuid))
            if p.get("format") in {"REEL", "SHORT"}:
                doi = p.get("doi")
                if not doi or (network, doi) in reel_dois:
                    errors.append("Duplicate DOI+video within " + network + ": " + str(doi))
                reel_dois.add((network, doi))
                for digest in video_files(p).values():
                    if (network, digest) in video_hashes:
                        errors.append("Duplicate video bytes within " + network + ": " + str(pid))
                    video_hashes.add((network, digest))
            if network == "youtube":
                if not youtube_enabled:
                    errors.append(str(pid) + ": YouTube receipt exists while destination disabled")
                youtube_check(root, p, posts, releases, now, errors)
        if status in RESERVED:
            try:
                date = local_date(p["publication_date"])
                if date.year == now.year and date.month == now.month:
                    count += 1
            except (KeyError, ValueError, TypeError):
                errors.append("Missing or invalid publication date: " + str(pid))
    limit = config.get("monthly_publication_cap", 20)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 < limit <= 20:
        errors.append("Monthly cap must be an integer no larger than 20")
        limit = 20
    if count > limit:
        errors.append("Monthly conservative post reservations exceed free plan cap")
    if count > 18:
        warnings.append("Only two or fewer calendar reservations remain")

    observed_used = 0
    observed_published_keys = None
    if youtube_enabled:
        quota = publisher.get("quota", {})
        try:
            observed = local_date(quota["observed_at"])
            observed_used = quota["observed_used"]
            observed_published_keys = quota["observed_published_post_ids"]
            if (quota.get("month") != now.strftime("%Y-%m") or
                    not isinstance(observed_used, int) or isinstance(observed_used, bool) or
                    observed_used < 0 or observed_used > limit or
                    not isinstance(observed_published_keys, list) or
                    any(not isinstance(k, str) or ":" not in k for k in observed_published_keys) or
                    len(set(observed_published_keys)) != len(observed_published_keys) or
                    len(observed_published_keys) > observed_used or
                    now - observed > HEARTBEAT_MAX_AGE or
                    observed > now + timedelta(minutes=15) or
                    quota.get("observation_basis") != "Metricool planner counter"):
                raise ValueError("Invalid quota observation")
        except (KeyError, ValueError, TypeError):
            errors.append("Fresh monthly Metricool planner counter observation required")
            observed_used = 0
    months = {(now.year, now.month)}
    for p in posts:
        if p.get("status") in RESERVED:
            try:
                due = local_date(p["publication_date"])
                if (due.year, due.month) >= (now.year, now.month):
                    months.add((due.year, due.month))
            except (KeyError, ValueError, TypeError):
                pass
    budgets = [month_budget(posts, now, year, month,
                           observed_used if (year, month) == (now.year, now.month) else 0,
                           observed_published_keys if (year, month) == (now.year, now.month) else None)
               for year, month in sorted(months)]
    for budget in budgets:
        budget["available_youtube_slots"] = max(0, limit - budget["projected"])
        if budget["projected"] > limit:
            errors.append(budget["month"] + ": destination reservations plus protected "
                          "remaining Instagram slots exceed free plan cap")

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
                if (platform(p) != "instagram" or p.get("status") not in FINAL or
                        p.get("format") != fmt):
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
            publication_check(p, due, now, errors)
            release_check(root, p, releases, errors)
            if fmt == "CAROUSEL":
                if not any(platform(q) == "instagram" and q.get("format") == "REEL" and
                           q.get("doi") == p.get("doi") and
                           q.get("status") in FINAL for q in posts):
                    errors.append(p["post_id"] + ": companion Reel not found")

        if youtube_enabled:
            due = datetime.combine(monday + timedelta(days=1), time(10), tzinfo=ZONE)
            matches = []
            for p in posts:
                if platform(p) == "youtube" and p.get("status") in FINAL:
                    try:
                        if local_date(p["publication_date"]) == due:
                            matches.append(p)
                    except (KeyError, ValueError, TypeError):
                        continue
            rows.append({"slot": "tuesday_youtube", "due": due.isoformat(),
                         "post_id": matches[0].get("post_id") if len(matches) == 1 else None,
                         "status": matches[0].get("status") if len(matches) == 1 else "missing"})
            if len(matches) != 1:
                errors.append("tuesday_youtube: expected exactly one active SHORT at " +
                              due.isoformat() + ", found " + str(len(matches)))

    report = {"ok": not errors, "checked_at": now.isoformat(),
              "week_start": monday.isoformat() if monday else None,
              "basis": "committed ledger receipts, NOT live Metricool availability",
              "reserved_month": count, "limit": limit,
              "monthly_budgets": budgets,
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
