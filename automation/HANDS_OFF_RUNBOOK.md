# Toxic Tales automatic production and publishing

Current owner instructions: 13 November 2026. Read automation/REELS_ONLY_POLICY.md and automation/config.json first. This document contains the active runbook; superseded instructions are archived in automation/history/HANDS_OFF_RUNBOOK_pre_cleanup_2026-11-13.md.

## Scope and schedule
Only akshaymohan16/toxic-tales-library; Metricool brand 7937614; Instagram @toxic_tales_eco; YouTube UCDvftxMMdtGSntm-ezcPfCg. No other accounts or repositories. Hard EUR 0 additional cost: connected Metricool MCP, standard free public GitHub Actions, GitHub Pages and existing free local models only.

Two distinct-paper videos per week. The same approved MP4 goes to BOTH Instagram Reels and YouTube Shorts on Tuesday and Friday, 10:00 Europe/Vienna, DST-aware. Four destination publications weekly, normally 16-18 monthly. Never create or publish a new carousel, static post, backfill or extra catch-up post except the exact owner-authorized one-off below. Keep previously published history. TT-002-CAROUSEL stays retired; TT-003 stays rejected.

The owner's later request for a new video today overrides the earlier no-13-November transition only for TT-008-REEL on Instagram and TT-008-YOUTUBE-SHORT on YouTube, both Friday 13 November 2026 at 18:00 Europe/Vienna. Authorization was recorded at 2026-11-13T13:20:50+01:00; this is a recorded acknowledgment time, not a claimed original message timestamp. automation/config.json owner_authorized_one_off_slots contains the two exact identities, formats, platforms and aware publication timestamps. This changes cadence eligibility only. All science, release, public-file, quota, ownership, intent, duplicate and provider-readback gates still apply. No implicit extension to other posts or dates. Do not create or retry an unsent one-off at or after its due time; reconcile any existing or uncertain provider receipt instead. Preserve both reservations for TT-007 bumblebees on Tuesday 17 November at 10:00 and the regular Tuesday/Friday cadence afterward.

Use only the existing Sunday producer 6aeefcb926708191b092554230783da1 and daily publisher Automation_991690d6af648191ac8037cfa96c92a0. Do not create competing posting tasks. The first-run audit is read-only.

Sunday 10:00: create and schedule the upcoming week's missing videos.
Monday: check and recover missing destinations; report first-run readiness after the Monday 18:15 check.
Daily 10:15 and 18:15: reconcile live provider state, recover routine failures, record a fresh heartbeat, issue deduplicated result notifications.

## Idempotent production
Resolve the next Tuesday/Friday slots from the current ledger and LIVE Metricool calendar before selecting papers. An existing approved video reserved for both destinations counts toward that week's two videos. Produce ONLY missing distinct-paper videos, not two additional videos on top of an occupied slot. Resume incomplete production before starting another candidate. Preserve existing reviewed media and successful provider reservations. Maintain one reserve week when practical, without extra publications or quota overruns.

Screen at least six varied peer-reviewed ecology/ecotoxicology candidates for genuinely missing story slots. Check duplicates against past and queued DOIs. Read selected original full texts, corrections/retractions, design, controls, replication, dose/units, uncertainty and conflicting evidence. Record claim-level sources and limits. Prepare story, narration, captions, licensed assets and pronunciations. Do routine editorial decisions without owner approval.

Apply quality/SCIENCE_JOURNALISM.md, PRODUCTION_STANDARD.md, VISUAL_STANDARD.md, EDITORIAL_REVIEW_SCHEMA.md, VISUAL_UPGRADE_2026-11.md, BRANDING_STANDARD.md and MOTION_STANDARD.md. Historical commentary in MEMORY.md/OPERATIONS.md cannot override current cadence or authorization.

Use scripts/build_current.py with nature-motion-10. The current entrypoint dispatches current source-specific scenes and delegates legacy episodes to the unchanged scripts/build_motion.py implementation, preserving frozen release fingerprints and exports. Develop source-specific scenes when needed; never downgrade to a generic slideshow. Preserve the real logo, neural voice, captions, scientific uncertainty and actual rights. Actual study footage and reference footage must be labelled accurately. Never animate invented measurements.

Run python automation/enforce_reels_only.py before production. Render on standard GitHub-hosted runners so video creation does not require the owner's computer. A push touching episode/evidence/quality/renderer files triggers .github/workflows/publish-library.yml. Inspect actual run jobs/logs; never equate a committed request with a completed render. Use a separate reviewer to inspect the actual encoded export, all scenes/transitions and phone-scale text, and verify audio/ASR and critical terminology. Never claim playback/listening/review that did not occur. Failed review means repair or another candidate, not bypass.

Bind releases to exact source and encoded-file hashes. After build run python automation/enforce_reels_only.py --sanitize-queue. The publication ledger controls current dates; never modify frozen episode sources just to reschedule. Preserve released bytes. Verify successful build/deployment and exact anonymous public MP4/cover bytes before scheduling.

## Quota and safe submission
Before EVERY create/reschedule, fetch the complete applicable month from Metricool and reconcile against automation/publisher-status.json and automation/published.json. Retain an append-only union of published network:UUID identities, including deleted provider entries; numeric IDs may change. Reconciled use = max(baseline.used + count(keys not in baseline), count(all keys)). Never double-count baseline items or reduce known usage. On a genuinely new calendar month use a new zero-reset baseline and the complete month's calendar. Save true observation time, baseline, keys and full_month_calendar_verified=true. Fresh reconciliation suffices; browser meter access is optional.

Reserve ALL remaining Tue/Fri slots on both networks, both exact owner-authorized one-off destinations even before receipts exist, exceptional existing commitments and uncertain writes. Count each reserved one-off only once after its receipt exists. Published + reserved destinations must remain <=20 in each month. Missing or contradictory evidence blocks that submission. Never upgrade or pay to recover.

Use separate Instagram-only and YouTube-only items with identical approved MP4 bytes. Hosted URLs belong in info.media/videoThumbnailUrl; omit mediaFiles. YouTube requires title, description/DOI/source/credits, type=short, public privacy, madeForKids=false after audience review and synthetic-narration disclosure. Keep autoPublish=true and draft=false. On updates preserve destination-specific tags/fields but omit data blocks for disabled networks.

Persist submission intent before provider writes. Read back date/time/timezone, provider, UUID, media, metadata and flags after each successful write. Reconcile uncertain writes/timeouts before retrying. Never blindly create a duplicate. Repair only the failed/missing destination.

## Run ownership
Before creating a story for an empty slot or submitting a provider item, acquire its claim in automation/claims.json. Use keys production:YYYY-MM-DD for a video slot and submission:PLATFORM:YYYY-MM-DDTHH:MM:TIMEZONE for a destination. Record a unique owner_run_id (task ID plus actual run-start timestamp), phase, claimed_at, expires_at, source/DOI/release fingerprint when known, and intent/UUID when present. Production claims last at most four hours; submission claims at most thirty minutes.

Claim acquisition is a GitHub compare-and-swap: fetch current main and claims, create the new tree/commit against that exact parent, then update main with expected_sha set to that parent and force=false. If rejected, re-fetch and inspect; do not submit. Re-read the claim before the external write. Skip another run's unexpired claim. An expired, abandoned or uncertain claim is NOT permission to retry: first reconcile live Metricool, submission intent and ledger, then atomically take ownership only if no write could be duplicated. Persist receipts and mark a successful claim complete; keep uncertain writes marked uncertain until resolved. A producer crash must never erase an intent. Claims are coordination evidence, not provider idempotency keys.

## Publication, website and alerts
PENDING means processing/scheduled, not published or failed. After the due time require provider PUBLISHED plus expected live content/channel URL before declaring publication. Preserve successful destinations while investigating failures. Persist publication receipts and URLs in the ledger; build/deploy the archive after receipt changes.

Each video's source page must include citation, DOI/full-text link, claim evidence, limitations and asset credits before scheduling. The archive must display confirmed Instagram/YouTube links after publication. Link papers; never republish publisher PDFs. The archive enhancement step runs before site hashes are generated.

Send a creation notification once each new video is released, public and reserved on both platforms: title, one-sentence summary, DOI, preview/source link and publishing date. Combine videos completed in the same run into one message; do not withhold a finished video's alert because another remains incomplete. This is a creation/scheduling result, not publication. Record release-fingerprint identity in automation/notifications.json.

After actual publication, notify once with the available Instagram/YouTube links. Group simultaneous confirmations; report partial publication honestly and notify the remaining destination when later verified. Deduplicate publication by platform:UUID. Send a new genuine owner-action blocker once; suppress unchanged routine status. Task-result delivery is configured, while push/email receipt cannot be assumed.

## Recovery and proof
Every daily run must inspect actual Metricool, recent GitHub failures and open 'Toxic Tales readiness:' issues, repair ordinary failures, then update publisher-status, inventory, ledger and current batch with truthful timestamps. Run automation tests and verify_readiness after state changes. The GitHub watchdog reads committed evidence only; a green run does NOT prove next week's production exists or that a scheduled post is live. Validate four provider receipts for the current local week's Tuesday/Friday directly at the Monday checkpoint.

If a dependency is temporarily unavailable, persist the exact phase, IDs, intent and next recovery action. A later run resumes it. Never turn a failed or partial batch into READY. Owner action is needed only where the external service requires it, such as expired authentication. Do not promise permanent failure-free operation.

Transition: the later owner request authorizes only the paired TT-008 one-off on Friday 13 November at 18:00 as recorded above; it supersedes the former no-backfill transition for that exact video and instant. Tuesday 17 November already has TT-007 on both platforms. Friday 20 November remains the next regular missing video until current live evidence says otherwise; resolve this dynamically, not from historical dates. Track one-off creation and confirmed publication notifications with the same deduplication rules as regular videos, and retain its evidence after the one-off date.
