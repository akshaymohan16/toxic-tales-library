# Weekly YouTube destination policy

Effective 8 November 2026 under the owner's explicit authorization for full routine automation. This is an extension of the existing Sunday producer and daily publisher, not a new task or posting loop. It supersedes older Instagram-only scope and three-receipt success wording only as described here.

## Destination and cadence
- Allowed repository: akshaymohan16/toxic-tales-library only.
- Metricool brand 7937614; Instagram toxic_tales_eco; YouTube channel UCDvftxMMdtGSntm-ezcPfCg, displayed as Toxic Tales. Re-read getBrandSettings before every scheduling action; an absent or different YouTube channel blocks YouTube only.
- Instagram stays Tuesday Reel, Thursday carousel, Saturday Reel at 10:00 Europe/Vienna with DST.
- Add only the Tuesday Reel as one YouTube Short each local week, at the same 10:00 time, starting 10 November 2026 with TT-006. Saturday videos and carousels have no YouTube destination. No historical backfill.
- Keep a separate YouTube-only Metricool item and ledger row so descriptions, receipts and recovery cannot overwrite Instagram. Never edit or delete existing Instagram reservations to add YouTube.
- Keep the existing producer 6aeefcb926708191b092554230783da1 and publisher Automation_991690d6af648191ac8037cfa96c92a0 with their current schedules. No additional publishing automation.

## Release and metadata
Read all existing scientific, editorial, visual, branding, audio, source/license and exact-file quality standards. Reuse the same approved video bytes and source identity; do not rerender frozen media merely to add a destination. Exclude TT-003, retired items and held drafts on both platforms. An Instagram release alone does not approve unreviewed YouTube text or rights.

Store a platform review bound to the exact source Reel post ID, release fingerprint and MP4 SHA-256. Write a clear accurate YouTube title of at most 100 characters and description of at most 5000 characters, preserving the focal DOI, research-record URL, material scientific limitations, actual media credits/licenses and synthetic/illustration disclosures. No private owner data, account email, tokens or publisher PDFs in public files. Recheck all video, audio, font and illustration rights for YouTube; do not assume Instagram music rights transfer. Adult/general-interest science content uses madeForKids=false after reviewing audience targeting; educational content alone is not a kids classification. Privacy is PUBLIC. Preserve appropriate AI/synthetic disclosure; set isAiGeneratedContent=true for the existing synthetic narration. Use explicit Shorts type and a vertical/square compatible approved MP4. Never stretch or crop an approved film without a new exact-file review.

Use the verified provider payload recorded with the first YouTube receipt as the connector template. Public URLs belong in info.media and info.videoThumbnailUrl; omit mediaFiles (local uploads). YouTube description belongs in top-level text; youtubeData carries title, type, privacy, madeForKids, and isAiGeneratedContent. Omit unrelated platform data. Any provider validation error is final for that input: inspect, reconcile, and repair the concrete problem; never blindly retry.

## Shared zero-cost quota
Metricool Free permits 20 published destination posts per calendar month. The same video on Instagram and YouTube consumes two. Drafts do not publish, but uncertain writes must be reserved until resolved.
Before every create/reschedule:
1. Observe the current planner usage counter and full-month calendar, including all platforms, past PUBLISHED receipts, future non-drafts, and uncertain submissions. Save minimal month/count/observation timestamp and basis.
2. Count each provider destination once. Do not add already-published ledger rows on top of the observed usage count.
3. Reserve ALL remaining Tuesday/Thursday/Saturday Instagram slots in that month, including weeks not produced yet. Deduplicate those planned slots against existing reservations. Reserve other already committed destinations and unresolved writes.
4. Admit YouTube only while the total, including the proposed Short, is at most 20. Also reserve later weekly Tuesday Shorts when planning the month. Standard cadence is 16-19 destinations per full month. If exceptional posts consume the buffer, skip/defer YouTube before allowing it to consume Instagram capacity; record quota_hold truthfully and retry only within a later permitted weekly slot. Do not accumulate extra backfill Shorts.
5. Never upgrade, buy credits, start trials, use paid API/runner/storage, or silently change Instagram cadence. Missing or stale quota evidence blocks new scheduling, not existing posts.

## Idempotency and receipt model
Existing ledger entries without platform mean instagram. New YouTube rows use post_id TT-NNN-YOUTUBE-SHORT, platform youtube, format SHORT, source_post_id TT-NNN-REEL, exact youtube_channel_id, DOI, release_fingerprint, source_files_sha256 and separate provider ID/UUID/planner URL/date/status. Store youtube metadata and review identity. One approved source may have one Instagram Reel and one explicitly authorized YouTube Short; that is intentional cross-platform distribution. Deduplicate within platform by stable post identity, DOI+video-format family, exact source/media hash, channel and weekly slot. A prior success on either platform never permits repeating it on that platform.

Before submission reconcile existing ledger and the actual provider calendar. Persist an in-progress intent with deterministic post/channel/source/date identity before the external write. On timeout/unknown result, reserve quota and inspect for the existing matching item; do not submit again until absence is established. Immediately save provider ID/UUID from success, then read the calendar back and verify the exact destination, time, media, title/description, Shorts type, PUBLIC privacy, audience, AI flag, autoPublish=true and draft=false. A scheduled PENDING receipt is not publication.

## Existing daily publisher and recovery
At 10:15 Europe/Vienna the existing publisher checks both destinations independently. Require positive provider PUBLISHED status and a video public URL, then verify the live YouTube video belongs to the pinned channel, has the expected title and playable expected content. Store live_verification with checked_at/url/channel_id/decision. A missing analytics row or disappearance from the scheduler is not proof of success or failure; YouTube analytics can lag. Keep scheduled/provider-published/live-verified states distinct.

For PENDING processing do not duplicate. Investigate overdue/FAILED items, recheck for an actual video before repair, and repair routine media/metadata/timing failures autonomously on the same destination. Reconcile ambiguous submissions by UUID and video identity. Do not touch successful Instagram while repairing YouTube. Notify once per platform/post only after confirmed live publication; report a new genuine service/account blocker when recovery is impossible. No routine owner approvals or weekly preparation are required.

Every Sunday finish next week's three Instagram reservations and one Tuesday YouTube reservation. Monday's independent check requires all four destination receipts unless a real documented quota/account block exists; a block must not be called READY. Update batches, publication ledger, current publisher heartbeat and minimal quota observations. Run the readiness verifier and inspect its GitHub incident. The GitHub watchdog checks committed evidence; the existing daily publisher remains responsible for fresh Metricool and live-platform checks.

## Verification boundary
Configuration and scheduling can be verified now; actual publication can only be verified after its future due time. Never claim an unattended production cycle succeeded merely because a task is active or a build passed. Preserve the existing 15 November results-report task and have it assess the current four-destination policy.

