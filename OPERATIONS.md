# Toxic Tales operations

## Scope, authority and cost
Only repository `akshaymohan16/toxic-tales-library`, Instagram `@toxic_tales_eco`, and Metricool brand `7937614` are authorised. Do not enumerate, read, alter or deploy another repository, especially Asellus Consortium. Keep credentials, private account fields and publisher PDFs out of this public repository.

The owner delegated routine research, editorial judgement, production, scheduling and publication on 7 November 2026. No weekly selections, draft approval, downloads or Publish clicks should be required from the owner. Use existing connections, standard free GitHub Actions runners, GitHub Pages and free local models. No purchases, paid APIs, subscriptions, upgrades or trials.

## Current specification
Read [quality/SCIENCE_JOURNALISM.md](quality/SCIENCE_JOURNALISM.md) and [quality/PRODUCTION_STANDARD.md](quality/PRODUCTION_STANDARD.md) before writing or reviewing new films. The owner rejected the TT-003 v4 methods/results summary; it must never become a quality benchmark. Reels need a complete contextual ecological story, not an experiment summary with background added. Direct eSpeak narration and fallback generic slideshows remain prohibited. Kokoro is the pinned neural voice; espeak-ng is only its phonemiser dependency.

New Reels use the revised `episodes/tt-003.json` science-journalism schema, `production.editorial_style=science-journalism` and `scripts/production.py`. Aim for 60-85 seconds, with a 45-95-second technical envelope. Frozen `scripts/production_v4.py` maintains the previously approved TT-002 assets without rerendering them; legacy TT-002 and retired TT-001 are not new-film templates. New papers need their own source-specific visuals and design. Adapt the renderer when the topic requires it; do not put fish/tank graphics into an unrelated ecological study.

## Recurring work
Two Reels from distinct published papers and one companion carousel per week: Tuesday, Thursday and Saturday respectively, at 10:00 Europe/Vienna with DST. The weekly producer researches and renders on Sunday; the daily publisher reconciles, schedules and repairs routine failures.

Read the current batch, release records, publication receipts and monthly inventory before acting. Keep TT-001 disabled. TT-002-REEL was published on 7 November 2026 and must not be reposted. A new distinct paper is assigned to Tuesday 10 November; retain TT-002-CAROUSEL on 12 November and TT-003-REEL on 14 November. Fill only unoccupied slots; maintain a prepared reserve when practical.

## Research and records
Screen at least six credible ecology/ecotoxicology papers, with varied organisms and ecological themes. Read selected original full texts. Verify citation/DOI, independent replication, controls, species, measured and nominal doses/units where relevant, result, uncertainty, causal scope and important limits. Check corrections/retractions and relevant subsequent conflicting evidence. Replace inaccessible evidence with another candidate.

Create `editorial_story` with question, why_it_matters, narrative_arc, context_sources and closing_payoff. Independently verify at least two published context sources where contextual claims are made. Explain the ecological relationship and stakes before presenting the study's contribution. Pair narration with explanatory visuals, integrate the pivotal limitation and return to the opening question. Never invent interviews, quotations, reactions or scenes. Companion carousels may focus on methods or limits.

Maintain evidence/<id>.md with exact claim source locations and verification date, episode JSON, dated screening/batch records, licences and media credits. Captions need the stable post ID, DOI, actual archive/credit URLs and material caveat. Do not claim link-in-bio until verified. No fabricated data, implied study footage or copied publisher figures.

## Build, inspect and release
Commit sources to this repository. The publish-library GitHub workflow renders, deploys and downloads the public files for exact-byte verification. Rendering is remote and must not depend on the owner's computer. For Windows source transport, scripts/export_sources.py emits ASCII-safe JSON; avoid shell output that normalises Unicode quotation marks.

The renderer produces site/qa/<id>.json, decoded frame contact sheets, source pages, candidates.json and a gated publish-queue.json. Inspect actual encoded frames at every shot, the cover and all carousel pages; use moving playback where available. Read the final audio transcript, critical-word/caption checks and loudness evidence. Listen when capability exists; never equate transcription or volume checks with a listening judgement. Keep full scientific negations together and check phone readability.

Write separate substantive scientific, visual and audio reviews in quality/releases.json tied to the exact fingerprint, evidence hash and all file hashes. For science-journalism films, a substantive `narrative_review` must also pass the story questions in SCIENCE_JOURNALISM.md; an accurate methods/results summary is insufficient. Changes invalidate approval. The current build/deploy/verify-public-media jobs must pass before scheduling. Use current public QA files with a commit query parameter if a browser cached an older response. A green build alone does not establish editorial quality or publication.

## Capacity and duplicate checks
Before each create, confirm brand handle/timezone and fetch the entire local-month calendar. The actual Metricool planner usage counter establishes current plan usage; add future scheduled destination posts and uncertain submissions as reservations. It showed 1/20 used on 7 November at 15:21 Europe/Vienna, with only Instagram connected. Update that observation when available. Empty newly connected analytics do not override it or prove zero history.

Use all observable history and the receipt ledger for duplicate checks. A carousel counts once; another network consumes another destination publication. Do not double-count scheduled items once published. Stay at or below 20/month, aiming for roughly 13; never buy an upgrade. Preserve dated minimal usage/receipt records without private account fields.

## Publication and monitoring
GitHub builds and hosts; Metricool publishes. Use exact released immutable URLs, autoPublish=true and draft=false. Instagram REEL uses MP4 plus JPEG cover; POST uses ordered carousel JPEGs. Include appropriate synthetic-media disclosure.

Save each confirmed receipt immediately in automation/published.json, including stable post ID, provider ID/UUID/planner URL, date, media URLs and exact hashes; read it back from the calendar. Reconcile an uncertain request before any retry. Do not overwrite unrelated posts. After the due time require positive PUBLISHED/provider public URL or live-post evidence. Disappearance from a schedule is not success.

Follow the standard's self-repair and missed-slot rules. Routine source, render, caption, caching and deployment problems are repaired autonomously; unsupported content is replaced. Never lower quality to fill a slot. Preserve paper records and media still needed by scheduled posts. For the Metricool connector, put public URLs in info.media and info.videoThumbnailUrl and omit the optional mediaFiles argument, which treats inputs as local upload paths. Record genuine service/account blockers and notify only when newly actionable. Expired account authentication can require owner action; it cannot be bypassed.
