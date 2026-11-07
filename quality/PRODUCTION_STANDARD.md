# Toxic Tales recurring production standard

Owner instruction, 7 November 2026: operate without routine owner work; maintain the rebuilt quality, use verified published ecology papers, keep paper records, and publish two Reels and one companion carousel weekly. The editor makes ordinary editorial decisions. Do not ask the owner to select papers, judge drafts, download media, or click Publish.

## Durable production path

Only `akshaymohan16/toxic-tales-library`, Instagram `@toxic_tales_eco`, Metricool brand `7937614`. No other repository. No purchases or paid rendering, TTS, API, stock-media or subscription services. Standard public-repository GitHub Actions runs the renderer, so the owner's computer need not be running. The scheduled ChatGPT producer researches and edits; the scheduled publisher reconciles and schedules through the connected Metricool service. Credentials are never written into the repository.

`scripts/production.py` is the maintained renderer. Kokoro af_heart 1.07 is pinned with model SHA-256 checks. espeak-ng is only a pronunciation/phoneme dependency; direct eSpeak audio is prohibited. There is no degraded slideshow or silent-voice fallback. Short scientific animation scenes, correctly identified reference imagery, caption phrases and source-specific diagrams are required. Rebuild automatically if any gate fails.

## Scientific checks before rendering

Read the full peer-reviewed original paper. Record title, authors, DOI, journal, year, full-text URL, date checked, exact source locations for each spoken or visual claim, independent replication, controls, species, exposure and measured versus nominal doses, results, uncertainty and causal limits. Check corrections/retractions and relevant subsequent contrary findings. Abstracts, news stories and generated summaries are discovery aids, never sufficient proof. An unavailable or ambiguous paper is replaced with another fully checked candidate. Never invent numbers, data points, research footage or mechanistic certainty.

Maintain `evidence/<id>.md`, the episode JSON, screening notes and a dated batch record. Each entry publishes a searchable paper record and a source/credit page. Link the DOI and archive in each caption. Store legal media credits, licence URLs, source URLs, modifications and download hashes. Do not redistribute publisher PDFs or assume that an image on a journal page is reusable.

## Editorial acceptance

The benchmark is the owner's original account, including the 31 May 2025 desert-locust Reel (`DKUQ1HUMjEB`), viewed in the 7 November integration session: organism-first opening, nature imagery, short shots, prominent readable captions. The rejected eSpeak TT-002 post and v2 slideshow are never a benchmark. Original audio parity was not established and must not be claimed.

The first sentence must make a specific intriguing, paper-supported ecological observation. The opening should show the organism/process, with no introductory logo card. Aim for 35–50 seconds; the technical envelope is 30–55 seconds. Use at least five relevant visual forms, generally 2–5-second shots, no shot over 7.5 seconds, and no long repeated aquarium/stock sequence. More than a token camera zoom is needed to call a scene animated. Main captions must fit within the phone safe region at a readable size. Avoid simultaneous redundant headline, paragraph and subtitles. Keep a scientific negation with the claim it qualifies. Explicitly label conceptual drawings; avoid invented point clouds or graphs that look like reported data. State the material caveat in the film itself. Use a concise, natural ending.

Every completed export requires actual encoded-frame inspection at each shot, all carousel pages and the cover. Inspect a moving playback when available; compare comprehension, pacing, topic-specific visuals and readability, not just technical success. Read the final ASR transcript and listen when listening capability exists. Never claim human listening from a volume or transcript check. The technical audio gate uses segment and final-export transcription, critical terms, speech/caption matching, approximately -16 LUFS and safe true peak. Pin the accepted voice and retain the transcript/loudness evidence. A material pronunciation or visual problem requires correction and a new review.

## Release and publication

The build creates `site/qa/<id>.json`, actual decoded contact sheets, the source archive and `candidates.json`. New candidates do not enter `publish-queue.json` until the editor writes a substantive `quality/releases.json` review with exact fingerprint, file hashes, evidence hash and separate scientific, visual and audio assessments. An episode, source or renderer change invalidates the release. Blank approvals or copied checkboxes are not reviews.

The current `verify-public-media` job must succeed for the exact deployed commit. It downloads the public files and compares them with the build, then checks their media properties. A previous build's green check is insufficient. Before scheduling, recheck queue files and release hashes, paper/credit availability, brand identity and calendar capacity. Preserve the immutable post ID and immediate Metricool receipt. On a timeout, reconcile before retrying; never blindly duplicate.

Metricool's planner monthly counter is authoritative for plan usage. On 7 November 2026 at 15:21 Europe/Vienna it showed 1 of 20 posts used. Brand settings showed only Instagram connected. Official reference: https://help.metricool.com/main-differences-between-free-and-paid-plans-bl0v9 (checked 7 November 2026). Add future scheduled destination posts and uncertain submissions as reservations, count a carousel once and cross-network publication separately, stay at or below 20. Empty newly connected Instagram analytics do not mean zero history and do not override an observed planner counter. Preserve monthly observations; distinguish native Instagram activity from plan usage. Use all observable publication history for duplicate checks.

Default slots: Tuesday Reel, Thursday carousel, Saturday Reel, 10:00 Europe/Vienna with DST. Keep two different papers per weekly pair of Reels; carousel adds methods or limitations. TT-001 remains retired. TT-002-REEL was already published on Saturday 7 November; never repost it. The renewed two-Reel weekly instruction means Tuesday 10 November needs a NEW paper, not the repaired duplicate. The Sunday producer fills that slot while retaining the 12 November carousel and 14 November recovery Reel.

## Recovery and monitoring

Sunday production fills the next week's missing slots and maintains a one-week prepared reserve when capacity and available evidence permit. Daily publisher also finishes pending technical/QA work and repairs failed runs using this standard; it may produce a missing paper under the same research requirements if the weekly producer failed. Select a different verified paper when the original is inaccessible; do not lower the evidence standard. Fix routine rendering, caching, caption, asset and deployment errors autonomously. Never publish a failed item merely to meet the calendar. If a deadline is missed, use the next unoccupied day at 10:00 within the same week, at most one post daily, preserving the weekly format balance and avoiding duplicates. Do not overwrite unrelated posts.

After the scheduled time, require positive provider status/public URL or live post evidence. A schedule disappearing is not proof of publication. Record confirmed success, failures, retries and unchanged uncertainty. Retry after a changed condition. Keep the owner uninvolved in routine work; send a concise batch digest or a new actionable service/account blocker. Never claim an automation completed just because it is enabled.
