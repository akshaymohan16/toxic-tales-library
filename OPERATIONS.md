# Toxic Tales operations

## Absolute project boundary
ONLY `akshaymohan16/toxic-tales-library` is authorised. Do not enumerate, read, copy, edit, deploy or repurpose any other repository, especially the unrelated Asellus Consortium site. Only Instagram @toxic_tales_eco / Metricool brand 7937614 is the publishing target. Keep credentials, private messages/account data and publisher PDFs out of this public repository.

## Delegation and cost
On 7 November 2026 the user explicitly delegated ordinary topic selection, scientific review, production and posting without routine approval. Do not ask for weekly selections, editing or sign-off. Stop rather than publish uncertain science. Notify only concise new batch results or genuine new blockers; suppress repeat unchanged alerts. Expired authentication may still require account-owner action: do not promise that can be bypassed.

Use existing ChatGPT/Metricool connections, standard free GitHub-hosted Linux runners in this public repository, GitHub Pages, and offline eSpeak/FFmpeg/Pillow. No subscriptions, purchases, paid APIs/credits, upgrades, larger runners or paid trials. The renderer makes schematic narrated motion graphics, not cinematic generative footage. Keep the original cinematic pilot separate.

## Deployment
Pages activation is complete. Build, deployment and anonymous media verification passed on 7 November 2026. Repeat verification for every changed batch: source commits and build success are not evidence of a public deployment. `scripts/verify_live.py` downloads the actual Pages files without authentication, checks exact build hashes, dimensions/codecs/duration/audio, and creates contact sheets and `report.json` in the `toxic-tales-live-verification` artifact. Use a successful current artifact and inspect its downloaded media when direct chat network access is unavailable. Reject stale reports. Configuration flags alone are not proof.

The library is https://akshaymohan16.github.io/toxic-tales-library/ . Each episode has a stable `#slug` anchor, original DOI, summary, limitations and media. New reviewed episodes update it automatically. The existing Instagram bio/Linktree has NOT been changed or verified. Do not say link-in-bio unless `bio_link_confirmed` becomes true. Include actual DOI and library URLs in captions meanwhile. Never create a paid link-management service.

## Editorial cycle
Target TWO 35–50-second Reels from two distinct source-checked papers and ONE 5–8-slide companion carousel per week, about 13 posts monthly. Default future slots: Tuesday Reel A, Thursday carousel, Saturday Reel B, 10:00 Europe/Vienna with the correct DST offset. Read `automation/batches` and episode posts first: fill only unoccupied upcoming-week slots. A manual/immediate run and a Sunday run must not create duplicate batches. Keep TT-001 disabled.

Screen at least six credible candidates; do not mistake screening for full verification. For selected studies read original full texts and verify DOI/title/authors, independent experimental units, controls, organism, measured versus nominal dose and units, findings, causal scope and important limits. Check corrections/retractions and relevant later contrary evidence. Keep traceable source locations in `evidence/<episode-id>.md`. If important evidence is inaccessible, choose another source. Flags are set true only after actual review. No fabricated citations/effect sizes, copied publisher figures, or invented experimental footage. Older studies must not be described as new discoveries.

## Episode format
Follow `episodes/tt-001.json` structurally without enabling it. Unique ID/slug; required source metadata; `review_status=verified`; actual check flags; 5–9 scenes, each headline/speech; optional 5–8 slides. Roughly 90–120 spoken words. Available graphics: fish, choice, caveat, river; other kinds are abstract waves. Choice is specifically a clean/drug-water diagram and must never be reused for unrelated designs. Graphics must not imply data that were not measured.

`publication_enabled=true` means scientifically reviewed candidate, NOT permission to bypass technical or capacity gates. Each post needs stable ID, REEL/CAROUSEL format, future offset-aware publication_date, caption <=2200 characters including DOI, source link and material caveat. Disclose synthetic/generated media appropriately. Inspect actual rendered text/layout and caption/narration consistency, not just the source JSON.

## Automatic inventory and quota guard
Before EVERY Metricool create, confirm brand/handle/timezone and query ALL scheduled posts for the target local calendar month, not just our entries. Query published feed posts, Reels and available Stories, including native/manual posts; cross-check aggregate counts and existing receipts. Discover current metric IDs rather than guessing. Preserve minimal monthly counts/IDs in `automation/inventory` so a 31-day month does not lose its first day to a rolling history window. Do not expose private account fields.

Deduplicate by immutable platform IDs and stable post IDs; a carousel is one publication, companion Reel/carousel are intentional distinct formats. Do not double-count scheduled items that became published. Include future queue reservations and unresolved submissions when calculating projected usage. Count other connected-network usage if it shares the allowance. Target about13 and never exceed20; leave a gap rather than buy an upgrade.

Missing/uninitialised/truncated/stale/error results are not zero. Metricool normally retrieves 30 days of initial history and syncs nightly, but pre-connection Stories cannot be recovered and Instagram-login connections may not expose Story metrics. Distinguish known API coverage limits from temporary sync; do not claim complete visibility or wait forever for data the API cannot provide. When required capacity cannot be established, hold scheduling, recheck automatically, and report a genuinely persistent blocker rather than seek routine approval. The free service's own quota and our conservative observed-account tally are distinct; do not assert unavailable historical native Stories consumed a Metricool publishing credit.

## Publishing and reconciliation
GitHub only renders/deploys/verifies; it never calls Instagram. The Sunday producer writes reviewed content. The daily publisher alone schedules after evidence, public-media, duplicate and capacity checks. Never use local sandbox paths as public media. Use autoPublish=true/draft=false, REEL with public MP4 and JPG cover, or POST with ordered carousel JPGs. Preserve all unrelated posts.

Record confirmed create receipts immediately in `automation/published.json` (stable ID, Metricool ID/UUID, time, planner URL, source/media IDs). Re-read schedules to confirm. If submission times out or is ambiguous, reconcile BEFORE retrying; do not duplicate. Never silently roll missed dates forward. After the due time, obtain positive published-state evidence and timestamp/URL from analytics; disappearing from the schedule is not publication. Allow sync lag, flag persistent failures, and never silently resubmit a possibly published item.

## Maintenance
Caching skips unchanged media. Build halts near900MB; preserve source entries and media for queued posts. No deleting sources to free space without a safe retention plan. Failed workflows, stale public URLs or unavailable evidence block publication. Check `automation/publisher-status.json` and current batch records for outstanding holds; do not treat technical completion as publication.
