# Toxic Tales operations

## Non-negotiable project boundary
The ONLY authorised repository is `akshaymohan16/toxic-tales-library`. Do not browse, read, copy, edit, deploy or repurpose any other repository. Discovery must target this exact repository, not enumerate unrelated repositories. This project is newly created and independent. Only use assets made for Toxic Tales or appropriately licensed originals. Never publish credentials, private messages, private account data or publisher PDFs.

## Zero additional cost
Use standard GitHub-hosted Linux runners on this public repository, free GitHub Pages, local eSpeak/FFmpeg/Pillow, and the user's existing ChatGPT and Metricool connections. No API subscriptions, credits, upgrades, larger runners, trials requiring payment, or purchases. The renderer is synthetic narrated motion-graphics, not a cinematic generative-video service. Keep the original cinematic pilot separate; do not claim the generic renderer reproduces it.

## One-time activation
In this repository only, open Settings → Pages and choose GitHub Actions under Build and deployment → Source. Re-run the deployment workflow if the first attempt failed because Pages was not enabled. The connector can commit source files but does not expose the repository Pages-administration operation. Do not request a password or personal access token in chat.

Confirm a successful deploy and anonymously fetch the site's index, health.json, papers.json, publish-queue.json, a complete MP4 and all carousel JPGs. Inspect video frames, dimensions, narration/subtitle timing and slide readability. Only then set `automation/config.json` deployment_verified to true. Check current live health on every publishing run even after the flag is true.

Once the site is verified, add ONE permanent link to the existing Linktree: Research Behind Toxic Tales. Do not create a new Linktree account or pay for link-management automation. Set bio_link_confirmed only after the user confirms the link; until then include the actual library/source URLs rather than saying link in bio.

## Editorial cycle
Target two original source-checked papers each week. Create a Reel for each and one 5–8-slide carousel that adds methods, evidence and caveats rather than merely duplicating a script. Defaults: Tuesday Reel A, Thursday carousel, Saturday Reel B at 10:00 Europe/Vienna; adjust only with good account-specific evidence. Each post needs a source-library entry, an honest caption and a stable ID. Stay at or below 20 total Instagram publications in any calendar month, including existing queued and published content.

Read original full texts, not only summaries. Verify DOI/title/authors, experimental unit and independent replication, controls, organisms, dose/unit, causal scope, exact quantitative results and major limitations. Check for corrections/retractions. If full text or essential evidence is unavailable, choose another paper or stop. Record the evidence and exact source locations in `evidence/<episode-id>.md`. Do not mark check flags true without actually checking. Study approval and technical success are different.

## Episode JSON
Use `episodes/tt-001.json` as a structural example. The pilot has publication_enabled=false and no posts; it is a deployment demonstration, not automatically approved for Instagram. New stories require unique IDs/slugs, source metadata, checks, review_status=verified, 5–9 scenes, and optional 5–8 slides. Scene kinds available: fish, choice, caveat, river (other kinds use abstract waves). Do not use fish/choice diagrams for unrelated mechanisms. Speech across the episode should be about 90–120 words. Renderer checks limits but cannot determine scientific accuracy.

Set publication_enabled=true only for verified publishing candidates. A posts item has: id, format (REEL or CAROUSEL), publication_date (ISO 8601 with the correct Vienna UTC offset), and caption (maximum 2200 characters, with DOI and episode ID). The caption must retain material caveats. Any realistic generated/synthetic imagery must be declared through the platform's appropriate setting. Synthetic narration is disclosed on the source library. Review platform disclosure requirements for each candidate.

Example post shape, with dates replaced by actual future dates:
```json
{"id":"TT-002-REEL","format":"REEL","publication_date":"2026-11-10T10:00:00+01:00","caption":"TT-002 — Your checked caption, source DOI and library URL."}
```

## Build and publication separation
Committing reviewed episode files triggers GitHub Actions to render, cache and deploy. The scheduled ChatGPT authoring task does not assume the deployment has finished. A separate publisher checks the live queue after deployment. The GitHub workflow NEVER contacts Instagram or calls paid APIs.

Before each Metricool write, fetch brand settings and current scheduled posts. Confirm @toxic_tales_eco and brand 7937614. Check `automation/published.json`, exact episode/post IDs in captions, and matching media/date; reconcile any uncertain previous result instead of posting twice. Do not schedule past dates, skip gates, remove source references or modify unrelated posts. Use autoPublish=true; REEL needs a public MP4, optional JPG thumbnail; carousel uses POST with the ordered JPG URLs. Maintain the brand timezone from Metricool. Record a successful API receipt with post ID/UUID, chosen time, planner URL and source IDs in automation/published.json. A scheduling receipt proves scheduling, not eventual publication.

If an API returns unknown or fails after submission, read the schedule before retrying. If media, evidence, monthly capacity, authorisation, deployment or connection is missing, stop and report the blocker. Never upgrade. Never say posted without published-state evidence.

## Maintenance
The cache skips unchanged videos. Build halts near 900 MB so storage can be managed before free hosting limits. Do not delete existing source entries. If retention changes are needed, preserve source pages and all media for queued posts. Workflow failures and stale/missing public URLs block posting.
