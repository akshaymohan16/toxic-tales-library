"""Record/identity gates for editorial review, not a model of story quality.

The judgement itself must be performed by an editor. These checks ensure that
required observations exist and refer to the current source or final files.
"""
import copy
import hashlib
import json

STANDARD = 'story-first-v1'
CHECKS = ('cold_viewer', 'story', 'visuals', 'payoff', 'scope', 'retelling')
STORY_FIELDS = ('audience', 'subject', 'setting', 'opening_context',
                'normal_expectation', 'story_selection', 'decisive_limit')
FROZEN_EPISODES = {'TT-002', 'TT-003'}
PLACEHOLDERS = {'pass', 'passed', 'checked', 'ok', 'okay', 'yes', 'tbd', 'todo',
                'n/a', 'none', 'placeholder'}


def _text(value):
    return (isinstance(value, str) and bool(value.strip())
            and value.strip().lower() not in PLACEHOLDERS)


def editorial_source_sha256(ep, evidence_text):
    """Stable source identity; review metadata cannot sign its own hash."""
    source = copy.deepcopy(ep)
    source.pop('editorial_review', None)
    if isinstance(evidence_text, bytes):
        evidence_text = evidence_text.decode('utf-8')
    payload = {'standard': STANDARD, 'episode': source,
               'evidence_text': evidence_text}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                                     sort_keys=True, separators=(',', ':'))
                          .encode('utf-8')).hexdigest()


def _checks_ok(review):
    if not isinstance(review, dict):
        return False
    if review.get('standard') != STANDARD or review.get('decision') != 'pass':
        return False
    if not all(_text(review.get(k)) for k in ('reviewer', 'reviewed_at')):
        return False
    checks = review.get('checks')
    if not isinstance(checks, dict):
        return False
    for key in CHECKS:
        check = checks.get(key, {})
        if (not isinstance(check, dict) or check.get('decision') != 'pass'
                or not _text(check.get('finding')) or not _text(check.get('basis'))):
            return False
    return True


def validate_pre_render(ep, evidence_text):
    """Fail closed for new sources; return the reviewed source hash.

    Frozen historical assets may remain accessible. TT-003 remains held and is
    not an approved template; a new publication-enabled revision must migrate.
    """
    plan = ep.get('production', {})
    if ep.get('id') in FROZEN_EPISODES and plan.get('editorial_standard') != STANDARD:
        assert ep.get('id') != 'TT-003' or not ep.get('publication_enabled'), \
            'Rejected TT-003 cannot be enabled without the current editorial standard'
        return None
    assert plan.get('editorial_style') == 'science-journalism', \
        'New films must use the science-journalism production path'
    assert plan.get('editorial_standard') == STANDARD, \
        'New films require the mandatory story-first editorial standard'
    story = ep.get('editorial_story', {})
    for key in STORY_FIELDS:
        assert _text(story.get(key)), 'Missing substantive editorial_story.' + key
    visuals = story.get('visual_plan')
    assert isinstance(visuals, list), 'Missing paired narration/visual plan'
    expected = set(range(1, len(plan.get('segments', [])) + 1))
    assert {v.get('segment') for v in visuals} == expected and len(visuals) == len(expected), \
        'Visual plan must cover every narration segment exactly once (1-based)'
    for visual in visuals:
        assert all(_text(visual.get(key)) for key in
                   ('visual', 'purpose', 'source_or_concept', 'accuracy_note')), \
            'Each visual needs purpose, provenance and an accuracy note'
    review = ep.get('editorial_review', {})
    source_hash = editorial_source_sha256(ep, evidence_text)
    assert _checks_ok(review), 'Incomplete pre-render editorial observations'
    assert review.get('source_sha256') == source_hash, \
        'Editorial review is stale: script, assets, evidence or story changed'
    return source_hash


def final_editorial_ok(release, manifest):
    """Require a separate export review and exact artifact/source identity."""
    if manifest.get('editorial_style') != 'science-journalism':
        return True  # Frozen pre-journalism history uses the existing exact-byte gate.
    if manifest.get('editorial_standard') != STANDARD or not isinstance(release, dict):
        return False
    review = release.get('final_editorial_review', {})
    if not _checks_ok(review):
        return False
    if review.get('independent_from_script_author') is not True:
        return False
    if review.get('reviewed_encoded_frames') is not True:
        return False
    if not manifest.get('editorial_source_sha256'):
        return False
    if review.get('source_sha256') != manifest['editorial_source_sha256']:
        return False
    if review.get('reviewer') == manifest.get('script_author'):
        return False
    return all(review.get(key) == manifest.get(key) and manifest.get(key)
               for key in ('fingerprint', 'files', 'evidence_sha256'))
