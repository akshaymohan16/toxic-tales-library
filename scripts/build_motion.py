"""Prospective motion entry point; the reviewed legacy build stays byte-exact.

Every new production episode must explicitly declare nature-motion-10.
The existing build, source, publication and exact-output gates run unchanged.
New motion exports additionally need their own independent, exact-file review.
Importing this module does not modify build or any frozen renderer globals.
"""
import copy
import hashlib
import types
from pathlib import Path

import build
import production_motion as motion_renderer
from motion_spec import validate_motion_spec
from preserve_releases import preserve_legacy_releases


MOTION_STANDARD = 'toxic-tales-motion-v1'
# These identities preserve existing exports, not a permission to remake them.
# The main preflight additionally verifies their exact source/release hashes.
FROZEN_LEGACY_EPISODES = frozenset({'TT-002', 'TT-003', 'TT-004',
                                   'TT-005', 'TT-006', 'TT-007'})
MOTION_CHECKS = ('kinetic_text', 'transitions', 'ecological_motion',
                 'camera_motion', 'evidence_bound_data', 'caption_sync')
MOTION_FRAME_CHECKS = ('reviewed_encoded_frames',
                       'reviewed_every_shot_and_transition', 'reviewed_phone_scale')
MOTION_DEPENDENCIES = ('scripts/production_motion.py', 'scripts/motion_spec.py',
                       'scripts/build_motion.py', 'quality/MOTION_STANDARD.md',
                       'requirements-motion.txt', 'scripts/preserve_releases.py')
PLACEHOLDERS = {'', 'pass', 'passed', 'checked', 'ok', 'okay', 'yes', 'tbd',
                'todo', 'n/a', 'none', 'placeholder'}


def select_renderer(ep):
    if ep.get('production', {}).get('renderer') == motion_renderer.DECLARED_RENDERER:
        validate_motion_spec(ep)
        return motion_renderer
    if ep.get('id') not in FROZEN_LEGACY_EPISODES:
        raise ValueError('New production episodes require nature-motion-10; '
                         'legacy renderers are reserved for exact archived exports')
    return build.select_renderer(ep)


def render_fingerprint(path, evidence_path, renderer, editorial_source):
    if renderer is not motion_renderer:
        return build.render_fingerprint(path, evidence_path, renderer, editorial_source)
    if not editorial_source:
        raise ValueError('Motion exports require a current story-first source review')
    # Reuse the full branded dependency set without editing the original hash
    # algorithm or any bytes contributing to scheduled/published exports.
    inherited = build.render_fingerprint(path, evidence_path,
                                         build.branded_renderer, editorial_source)
    digest = hashlib.sha256(('nature-motion-10\0' + inherited).encode('ascii'))
    for relative in MOTION_DEPENDENCIES:
        content = (build.ROOT / relative).read_bytes()
        digest.update(relative.encode('utf-8') + b'\0')
        digest.update(len(content).to_bytes(8, 'big'))
        digest.update(content)
    return digest.hexdigest()


def _substantive(value):
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def motion_review_ok(release, manifest, episode):
    """Validate provenance and review identity, never infer a quality judgement."""
    if not isinstance(episode, dict) or not isinstance(manifest, dict):
        return False
    if (episode.get('production', {}).get('renderer') != motion_renderer.DECLARED_RENDERER
            or manifest.get('declared_renderer') != motion_renderer.DECLARED_RENDERER
            or manifest.get('renderer') != motion_renderer.VERSION
            or manifest.get('motion_standard') != MOTION_STANDARD
            or manifest.get('motion_review_required') is not True):
        return False
    try:
        receipt = validate_motion_spec(episode)
    except (AssertionError, OSError, ValueError, TypeError, KeyError):
        return False
    if (manifest.get('motion') != receipt or not receipt.get('spec_sha256')
            or manifest.get('motion_spec_sha256') != receipt['spec_sha256']
            or manifest.get('evidence_sha256') != receipt.get('evidence_sha256')):
        return False
    provenance = manifest.get('motion_provenance', {})
    if (not isinstance(provenance, dict)
            or provenance.get('engine') != 'pillow-ffmpeg'
            or provenance.get('deterministic') is not True
            or provenance.get('paid_services') is not False
            or provenance.get('spec_sha256') != receipt['spec_sha256']):
        return False
    if not isinstance(release, dict):
        return False
    review = release.get('motion_review', {})
    if (not isinstance(review, dict) or review.get('standard') != MOTION_STANDARD
            or review.get('decision') != 'pass'
            or not all(_substantive(review.get(k)) for k in ('reviewer', 'reviewed_at'))
            or review.get('reviewer') == manifest.get('script_author')
            or review.get('independent_from_script_author') is not True
            or not all(review.get(k) is True for k in MOTION_FRAME_CHECKS)):
        return False
    for key in ('fingerprint', 'files', 'evidence_sha256', 'motion_spec_sha256'):
        if not manifest.get(key) or review.get(key) != manifest[key]:
            return False
    if (not manifest.get('editorial_source_sha256')
            or review.get('source_sha256') != manifest['editorial_source_sha256']):
        return False
    checks = review.get('checks', {})
    if not isinstance(checks, dict):
        return False
    for key in MOTION_CHECKS:
        check = checks.get(key, {})
        if (not isinstance(check, dict) or check.get('decision') != 'pass'
                or not _substantive(check.get('finding'))
                or not _substantive(check.get('basis'))):
            return False
    return True


def release_ok(release, manifest, episode=None):
    motion_declared = (manifest.get('declared_renderer') == motion_renderer.DECLARED_RENDERER
                       or manifest.get('renderer') == motion_renderer.VERSION
                       or 'motion' in manifest or 'motion_review_required' in manifest
                       or (episode or {}).get('production', {}).get('renderer')
                       == motion_renderer.DECLARED_RENDERER)
    if not motion_declared:
        # A missing episode or removed video-post entry cannot turn a future
        # film into legacy history. Companion carousels keep their format while
        # sharing the new episode's motion renderer and exact release checks.
        if (episode or {}).get('id') not in FROZEN_LEGACY_EPISODES:
            return False
        return build.release_ok(release, manifest, episode)
    if not motion_review_ok(release, manifest, episode):
        return False
    # The v9 branding gate hard-codes its renderer identities. Adapt ONLY those
    # two identity fields after checking the actual v10 identity and provenance;
    # every logo/layout, independent editorial and exact-file check is retained.
    adapted = copy.deepcopy(manifest)
    adapted.update(renderer=build.branded_renderer.VERSION,
                   declared_renderer=build.branded_renderer.DECLARED_RENDERER)
    return build.release_ok(release, adapted, episode)


def main():
    assert build.os.environ.get('GITHUB_REPOSITORY', build.REPO) == build.REPO, 'Repository boundary'
    preserved = preserve_legacy_releases()
    print('Preserved exact legacy exports:', ', '.join(preserved['preserved_episodes']),
          '; restored files:', preserved['restored_files'])
    # A private globals mapping avoids monkey-patching the historical build,
    # including when this module is imported by tests or preview rendering.
    namespace = dict(build.main.__globals__)
    namespace.update(select_renderer=select_renderer,
                     render_fingerprint=render_fingerprint, release_ok=release_ok)
    pipeline = types.FunctionType(build.main.__code__, namespace,
                                  'build_motion_pipeline', build.main.__defaults__,
                                  build.main.__closure__)
    pipeline()


if __name__ == '__main__':
    main()
