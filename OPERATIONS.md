# Toxic Tales operations

## Mandatory start of every session
Read [MEMORY.md](MEMORY.md), this file, [SCIENCE_JOURNALISM.md](quality/SCIENCE_JOURNALISM.md), [PRODUCTION_STANDARD.md](quality/PRODUCTION_STANDARD.md), [VISUAL_STANDARD.md](quality/VISUAL_STANDARD.md), and [EDITORIAL_REVIEW_SCHEMA.md](quality/EDITORIAL_REVIEW_SCHEMA.md) before selecting, writing, rendering, reviewing or scheduling content. These are operating requirements, not optional background. Carry the rejection history forward instead of using a rejected export as a benchmark.

**Current authority:** the owner has approved the story-first editorial approach and requested a new complete pilot. They have not approved that pilot or resumed publishing. Both recurring automations and future posts remain held. This hold overrides historical routine publication authority and every default slot below.

## Scope, authority and cost
Only repository `akshaymohan16/toxic-tales-library`, Instagram `@toxic_tales_eco`, and Metricool brand `7937614` are authorised. Do not enumerate, read, alter or deploy another repository, especially Asellus Consortium. Keep credentials, private account fields and publisher PDFs out of this public repository.

The owner's eventual goal is delegated routine research, editorial judgement, production, scheduling and publication without weekly selections, downloads or Publish clicks. The current pilot-review hold takes precedence. Use existing connections, standard free GitHub Actions runners, GitHub Pages and free local models. No purchases, paid APIs, subscriptions, upgrades or trials.

## Current specification
The owner rejected both the TT-003 methods/results summary and the subsequent pilot beginning “The fish were gone.” Neither is a quality benchmark. Reels need a complete contextual ecological story whose subject and situation are clear from the opening. Direct eSpeak narration and fallback generic slideshows remain prohibited. Kokoro is the pinned neural voice; espeak-ng is only its phonemiser dependency.

New Reels use `production.editorial_style=science-journalism` and `production.editorial_standard=story-first-v1`, with the paired storyboard and two-stage review described in EDITORIAL_REVIEW_SCHEMA.md. Treat the former 60-85-second target as a planning range inside the 45-95-second technical envelope, not an evidence-based engagement rule. A narrower complete story is preferable to racing through a broad one. Frozen assets preserve history without becoming new-film templates. New papers need their own source-specific visuals and design; adapt or select the renderer accordingly. Never put fish/tank graphics into an unrelated ecological study.

## Recurring work
After explicit resumption, two Reels from distinct published papers on Tuesday and Saturday, plus one companion carousel on Thursday, at 10:00 Europe/Vienna with DST. The weekly producer researches and renders on Sunday; the daily publisher reconciles, schedules and repairs routine failures.

Read the current batch, release records, publication receipts and monthly inventory before acting. Keep TT-001 disabled. TT-002-REEL was published on 7 November 2026 and must not be reposted. Historical November draft dates do not override the hold or authorise the rejected TT-003. Reconcile current assignments after the new pilot decision, preserving unrelated drafts. Fill only unoccupied slots with fully reviewed, distinct-paper stories; maintain a prepared reserve when practical.

## Research and records
Screen at least six credible ecology/ecotoxicology papers, with varied organisms and ecological themes. Read selected original full texts. Verify citation/DOI, independent replication, controls, species, measured and nominal doses/units where relevant, result, uncertainty, causal scope and important limits. Check corrections/retractions and relevant subsequent conflicting evidence. Replace inaccessible evidence with another candidate.

Create `editorial_story` with the original story fields and the additional mandatory audience, subject, setting, opening context, normal expectation, story selection, decisive limit and per-segment visual plan. Verify every contextual claim from published sources; use as many sources as the claims require, without an arbitrary minimum that encourages filler. At least the focal published original full text must be read. Establish an understandable ecological question, pair narration with explanatory visuals, integrate the pivotal limitation and fulfil the opening promise. Never invent interviews, quotations, reactions or scenes. Companion carousels may focus on methods or limits.

Before rendering, complete the six substantive editorial checks and compute the source hash. `validate_pre_render` must pass. An editor must actually assess cold-viewer comprehension, story continuity, visual explanation, payoff, scientific scope and a plain-language retelling. Placeholder prose, a methods/results recap and unsupported visual claims fail. Code checks the record and identity; it does not certify that a story is compelling.

Maintain evidence/<id>.md with exact claim source locations and verification date, episode JSON, dated screening/batch records, licences and media credits. Captions need the stable post ID, DOI, actual archive/credit URLs and material caveat. Do not claim link-in-bio until verified. No fabricated data, implied study footage or copied publisher figures.

## Build, inspect and release
Commit sources to this repository. The publish-library GitHub workflow renders, deploys and downloads the public files for exact-byte verification. Rendering is remote and must not depend on the owner's computer. For Windows source transport, scripts/export_sources.py emits ASCII-safe JSON; avoid shell output that normalises Unicode quotation marks.

The renderer produces site/qa/<id>.json, decoded frame contact sheets, source pages, candidates.json and a gated publish-queue.json. Inspect actual encoded frames at every shot, the cover and all carousel pages; use moving playback where available. Read the final audio transcript, critical-word/caption checks and loudness evidence. Listen when capability exists; never equate transcription or volume checks with a listening judgement. Keep full scientific negations together and check phone readability.

Write separate substantive scientific, visual, audio and narrative reviews in quality/releases.json tied to the exact fingerprint, evidence hash and all file hashes. New films additionally require `final_editorial_review`: an independent reviewer repeats the six editorial checks against the actual encoded export and records its source/file identity. `final_editorial_ok` must pass before release. Do not copy the pre-render review as evidence of final-film inspection. Script, evidence, asset, renderer or applicable standard changes invalidate the relevant approval. The current build/deploy/verify-public-media jobs must pass before scheduling. Use current public QA files with a commit query parameter if a browser cached an older response. A green build alone does not establish editorial quality or publication.

## Capacity and duplicate checks
Before each create, confirm brand handle/timezone and fetch the entire local-month calendar. The actual Metricool planner usage counter establishes current plan usage; add future scheduled destination posts and uncertain submissions as reservations. It showed 1/20 used on 7 November at 15:21 Europe/Vienna, with only Instagram connected. Update that observation when available. Empty newly connected analytics do not override it or prove zero history.

Use all observable history and the receipt ledger for duplicate checks. A carousel counts once; another network consumes another destination publication. Do not double-count scheduled items once published. Stay at or below 20/month, aiming for roughly 13; never buy an upgrade. Preserve dated minimal usage/receipt records without private account fields.

## Publication and monitoring
GitHub builds and hosts; Metricool publishes. Use exact released immutable URLs, autoPublish=true and draft=false. Instagram REEL uses MP4 plus JPEG cover; POST uses ordered carousel JPEGs. Include appropriate synthetic-media disclosure.

Save each confirmed receipt immediately in automation/published.json, including stable post ID, provider ID/UUID/planner URL, date, media URLs and exact hashes; read it back from the calendar. Reconcile an uncertain request before any retry. Do not overwrite unrelated posts. After the due time require positive PUBLISHED/provider public URL or live-post evidence. Disappearance from a schedule is not success.

Follow the standard's self-repair and missed-slot rules. Routine source, render, caption, caching and deployment problems are repaired autonomously; unsupported content is replaced. Never lower quality to fill a slot. Preserve paper records and media still needed by scheduled posts. For the Metricool connector, put public URLs in info.media and info.videoThumbnailUrl and omit the optional mediaFiles argument, which treats inputs as local upload paths. Record genuine service/account blockers and notify only when newly actionable. Expired account authentication can require owner action; it cannot be bypassed.
## Owner-reviewed visual pilot and notifications (7 November 2026)
The owner has explicitly requested a complete new pilot and will approve it before it may be posted. Both recurring automations and future Metricool posts are held. `automation/config.json` has publishing_paused=true, and rejected TT-003 remains publication_enabled=false. Do not treat approval of the editorial approach or a technical pass as permission to resume. The hold is lifted only after the owner approves the exact new pilot in chat. Reconcile the applicable draft and ledger before any update; do not attach a new paper to the rejected TT-003 identity or create a duplicate. Immediate posting requires the owner's requested go-ahead. Preserve unrelated drafts and the weekly balance when resuming.

The current preview at `pilot.html` must contain the exact candidate film, cover and full caption and link to that episode's `sources/<id>.html` paper citation, original full-text link, claim-source checks, limitations and media credits. Preserve old research records separately. The Instagram bio -> Linktree -> research archive chain was observed on 7 November 2026.

After approval and resumption, the daily publisher checks at 10:15 Europe/Vienna, after the 10:00 publication slot. For every newly confirmed PUBLISHED Reel, produce one concise notification with title, live Instagram URL, DOI and research-record URL. Record `publication_notification_reported_at` and `notification_post_id` only after producing the result message to prevent repeats. Scheduling is not publication. Do not claim push/email receipt: delivery depends on ChatGPT notification preferences and is not confirmed by the publisher API. Use the next daily check for late confirmations; no instant-delivery guarantee.

