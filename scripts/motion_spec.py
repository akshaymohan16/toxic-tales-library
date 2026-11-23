"""Fail-closed, evidence-bound inputs for the prospective motion renderer.

This validates provenance and exact counts, not the truth of a scientific claim.
The existing substantive source and independent export reviews remain required.
"""
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STANDARD = 'toxic-tales-motion-v1'
RENDERER = 'nature-motion-10'
KINDS = {'portrait', 'closing', 'nature', 'winter', 'cells', 'glucose',
         'experiment', 'scope', 'spider_bell', 'spider_oxygen', 'spider_probe',
         'spider_gas', 'spider_scope', 'bee_rolling', 'bee_path', 'bee_choice',
         'bee_age', 'bee_scope', 'bee_video', 'evidence_count'}
NUMBER_WORDS = dict(zip(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(),
    map(str, range(21))))


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def motion_spec_sha256(ep):
    # The whole production plan binds asset identity, timings, narration and scope
    # as well as animation choices. Review metadata cannot sign its own digest.
    return _digest({'standard': STANDARD, 'doi': ep['doi'],
                    'production': ep['production']})


def _text(value, name, maximum=300):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Missing or oversized motion ' + name)
    return value


def _number_tokens(text):
    return [NUMBER_WORDS.get(word, word) for word in re.findall(r'\w+|/', text.lower())]


def validate_motion_spec(ep):
    plan = ep['production']
    if plan.get('renderer') != RENDERER:
        raise ValueError('Motion renderer must be explicitly declared')
    spec = plan.get('motion')
    if not isinstance(spec, dict) or set(spec) != {'schema_version', 'evidence_sha256'} or spec['schema_version'] != 1:
        raise ValueError('Motion schema requires version 1 and exact evidence_sha256')
    evidence_path = (ROOT / ep['evidence_file']).resolve()
    if not evidence_path.is_relative_to((ROOT / 'evidence').resolve()) or not evidence_path.is_file():
        raise ValueError('Motion evidence must be an existing repository evidence record')
    raw = evidence_path.read_bytes()
    evidence_sha = hashlib.sha256(raw).hexdigest()
    if spec['evidence_sha256'] != evidence_sha:
        raise ValueError('Motion evidence hash is stale')
    evidence = raw.decode('utf-8')
    if ep['doi'] not in evidence:
        raise ValueError('Motion evidence must identify the focal DOI')
    claims = ep.get('evidence', {}).get('claims', [])
    for asset in plan.get('assets', []):
        if not re.fullmatch(r'[0-9a-f]{64}', asset.get('sha256', '')):
            raise ValueError('Motion assets require a pinned SHA-256: ' + str(asset.get('id')))
    metrics = []
    for si, segment in enumerate(plan['segments']):
        cursor = 0
        for qi, shot in enumerate(segment['shots']):
            start, end = shot.get('start', 0), shot.get('end', 1)
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in (start, end)):
                raise ValueError('Shot timing must be finite')
            if start != cursor or not 0 <= start < end <= 1:
                raise ValueError('Motion shots must cover each segment without gaps or overlap')
            cursor = end
            if shot.get('kind') not in KINDS:
                raise ValueError('Unknown/unbound motion scene: ' + str(shot.get('kind')))
            kind = shot['kind']
            source_doi = ('10.1371/journal.pone.0117234' if kind in
                          {'winter', 'cells', 'glucose', 'experiment', 'scope'} else
                          '10.1242/jeb.056093' if kind.startswith('spider_') else
                          '10.1016/j.anbehav.2022.08.013' if kind.startswith('bee_') else None)
            if source_doi and ep['doi'] != source_doi:
                raise ValueError('Source-specific ecological scene cannot be reused for another paper')
            motion = shot.get('motion', {})
            if not isinstance(motion, dict) or set(motion) - {'metric'}:
                raise ValueError('Unsupported per-shot motion option')
            metric = motion.get('metric')
            if shot['kind'] != 'evidence_count':
                if metric is not None:
                    raise ValueError('A metric requires an evidence_count scene')
                continue
            expected = {'label', 'value', 'total', 'unit', 'claim_index', 'source_quote', 'scope'}
            if not isinstance(metric, dict) or set(metric) != expected:
                raise ValueError('Evidence count requires exact value, denominator, scope and source binding')
            value, total = metric['value'], metric['total']
            if type(value) is not int or type(total) is not int or not 0 <= value <= total <= 30 or total < 1:
                raise ValueError('Evidence count must be integers: 0 <= value <= total <= 30')
            for key, limit in [('label', 42), ('unit', 24), ('scope', 110), ('source_quote', 600)]:
                _text(metric[key], key, limit)
            ci = metric['claim_index']
            if type(ci) is not int or not 0 <= ci < len(claims):
                raise ValueError('Unknown evidence claim index')
            claim = claims[ci]
            if not claim.get('claim') or not claim.get('location'):
                raise ValueError('Count claim needs an exact source location')
            quote = metric['source_quote']
            if quote not in evidence:
                raise ValueError('Count quotation is not verbatim in the pinned evidence record')
            tokens = _number_tokens(quote)
            patterns = ([str(value), 'of', str(total)], [str(value), '/', str(total)])
            if not any(any(tokens[i:i+3] == p for i in range(len(tokens)-2)) for p in patterns):
                raise ValueError('The evidence quote must state the exact numerator and denominator')
            # Require overlap with the named claim, in addition to the exact quote.
            if not set(re.findall(r'[a-z]{4,}', claim['claim'].lower())) & set(re.findall(r'[a-z]{4,}', quote.lower())):
                raise ValueError('Count quotation does not match its named claim')
            metrics.append({'segment': si, 'shot': qi, **metric,
                            'doi': ep['doi'], 'claim': claim['claim'],
                            'location': claim['location']})
        if cursor != 1:
            raise ValueError('Motion shots do not reach the segment end')
    return {'schema_version': 1, 'engine': RENDERER, 'standard': STANDARD,
            'evidence_sha256': evidence_sha, 'spec_sha256': motion_spec_sha256(ep),
            'metrics': metrics, 'measured_time_series': False,
            'animation_timing_represents_measurement': False}
