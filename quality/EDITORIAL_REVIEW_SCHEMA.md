# Mandatory editorial review record

Standard: `story-first-v1`, adopted by the owner on 7 November 2026. This is a record/identity gate, not an automatic engagement score. A filled record is not proof that the editor made a good judgement. The editor must actually perform the review described here and report limitations honestly.

## Before rendering

New episodes set `production.editorial_style="science-journalism"` and `production.editorial_standard="story-first-v1"`. In addition to the existing story fields, `editorial_story` contains substantive `audience`, `subject`, `setting`, `opening_context`, `normal_expectation`, `story_selection`, and `decisive_limit` text. `normal_expectation` may explain why a mystery does not require a familiar baseline; do not invent a public misconception.

`visual_plan` has one object for every narration segment, numbered from 1. Each contains `segment`, `visual`, `purpose`, `source_or_concept` and `accuracy_note`. It must explain how the image identifies, demonstrates, compares or explains the accompanying idea, with honest species/site/illustration limitations.

The episode's `editorial_review` object contains:

```json
{
  "standard": "story-first-v1",
  "source_sha256": "computed by editorial_source_sha256 after source is final",
  "reviewed_at": "ISO-8601 timestamp",
  "reviewer": "actual reviewer identity or role",
  "decision": "pass",
  "checks": {
    "cold_viewer": {"decision": "pass", "finding": "Specific assessment", "basis": "Opening line and matching shot"},
    "story": {"decision": "pass", "finding": "Specific assessment", "basis": "How named beats answer the central question"},
    "visuals": {"decision": "pass", "finding": "Specific assessment", "basis": "Actual planned visual explanations and asset limits"},
    "payoff": {"decision": "pass", "finding": "Specific assessment", "basis": "Opening promise compared with closing answer"},
    "scope": {"decision": "pass", "finding": "Specific assessment", "basis": "Claim locations and decisive caveat"},
    "retelling": {"decision": "pass", "finding": "The ecological insight in one plain sentence", "basis": "The important limit in one plain sentence"}
  }
}
```

The illustrative strings above are not acceptable review content. The reviewer must write observations specific to the proposed film. A failed or unclear item requires revision before rendering. `editorial_source_sha256` hashes the episode excluding only its review metadata, plus the exact evidence text and standard version. Thus a changed script, asset URL, credit, source claim, storyboard, caption or other episode content invalidates this review.

## After the final encode

The manifest includes `editorial_standard`, `editorial_source_sha256`, `pre_render_reviewer`, and `script_author` where known. Existing renderer/source/file hashes remain mandatory. Build fingerprints should include the current editorial gate and standards so a changed production rule cannot silently reuse an obsolete release.

`quality/releases.json` retains its existing scientific, visual, audio and narrative reviews. It additionally contains `final_editorial_review` with the same six checks and review metadata, plus:

```json
{
  "independent_from_script_author": true,
  "reviewed_encoded_frames": true,
  "source_sha256": "exact manifest.editorial_source_sha256",
  "fingerprint": "exact final manifest fingerprint",
  "files": {"media/example.mp4": "exact SHA-256", "media/example_cover.jpg": "exact SHA-256"},
  "evidence_sha256": "exact evidence-file SHA-256"
}
```

A separate reviewer must assess the actual exported film independently of the script author's own approval. Inspect each shot, the opening, transitions, ending, captions and cover; inspect moving playback when available. Review the final transcript and listen if the capability is available. Explicitly record what could and could not be inspected. Do not copy pre-render findings as if they were observations of encoded media. The film must pass the same cold-viewer and payoff tests after production; attractive images cannot repair a confusing script.

Code rejects stale or incomplete records. Code cannot verify honesty, expertise, comprehension, engagement or independence merely from these fields. The declared independence must reflect the real review process. No automated quality score is substituted for this work.

## Publication is a separate gate

The current owner-review hold remains active. An editorial pass, build success, new fingerprint or deployed preview does not authorise an Instagram post. The exact new pilot must be approved by the owner before posting. Rejected TT-003 remains archive-only until migrated and explicitly reconsidered; TT-002 must not be duplicated. All ordinary duplicate, usage, account and public-media verification gates remain in force.
