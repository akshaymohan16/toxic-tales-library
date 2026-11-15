"""Versioned TT-009 entrypoint. Delegate frozen TT-002..TT-008 unchanged.

New DOI-specific renderer adds no side effects to prior exact exports.
"""
import hashlib
import types
import build
import build_current as previous
import production_ants as ants

ANT_DEPENDENCIES = ('scripts/production_ants.py', 'scripts/build_next.py')


def _is_ants(episode):
    return (episode or {}).get('production', {}).get('scene_family') == ants.FAMILY


def select_renderer(episode):
    if _is_ants(episode):
        if episode.get('id') != 'TT-009' or episode.get('doi') != ants.DOI:
            raise ValueError('Ant renderer bound to the single research episode')
        ants.validate_motion_spec(episode)
        return ants
    return previous.select_renderer(episode)


def render_fingerprint(path, evidence_path, renderer, editorial_source):
    if renderer is not ants:
        return previous.render_fingerprint(path, evidence_path, renderer, editorial_source)
    inherited = previous.frozen_motion.render_fingerprint(
        path, evidence_path, previous.frozen_motion.motion_renderer, editorial_source)
    digest = hashlib.sha256(('cataglyphis-rescue-2009\0' + inherited).encode('ascii'))
    for relative in ANT_DEPENDENCIES:
        content = (build.ROOT / relative).read_bytes()
        digest.update(relative.encode('utf-8') + b'\0')
        digest.update(len(content).to_bytes(8, 'big'))
        digest.update(content)
    return digest.hexdigest()


def _ants_motion_review_ok(release, manifest, episode):
    namespace = dict(previous.frozen_motion.motion_review_ok.__globals__)
    namespace.update(validate_motion_spec=ants.validate_motion_spec, motion_renderer=ants)
    check = types.FunctionType(
        previous.frozen_motion.motion_review_ok.__code__, namespace,
        'check_ant_motion_review',
        previous.frozen_motion.motion_review_ok.__defaults__,
        previous.frozen_motion.motion_review_ok.__closure__)
    return check(release, manifest, episode)


def release_ok(release, manifest, episode=None):
    if not _is_ants(episode):
        if manifest.get('scene_family') == ants.FAMILY:
            return False
        return previous.release_ok(release, manifest, episode)
    if manifest.get('scene_family') != ants.FAMILY or manifest.get('scene_doi') != ants.DOI:
        return False
    namespace = dict(previous.frozen_motion.release_ok.__globals__)
    namespace['motion_review_ok'] = _ants_motion_review_ok
    check = types.FunctionType(
        previous.frozen_motion.release_ok.__code__, namespace, 'check_ant_release',
        previous.frozen_motion.release_ok.__defaults__,
        previous.frozen_motion.release_ok.__closure__)
    return check(release, manifest, episode)


def main():
    assert build.os.environ.get('GITHUB_REPOSITORY', build.REPO) == build.REPO
    preserved = previous.frozen_motion.preserve_legacy_releases()
    print('Preserved frozen legacy releases:', ', '.join(preserved['preserved_episodes']))
    namespace = dict(build.main.__globals__)
    namespace.update(select_renderer=select_renderer, render_fingerprint=render_fingerprint,
                     release_ok=release_ok)
    pipeline = types.FunctionType(build.main.__code__, namespace,
                                  'build_next_pipeline',
                                  build.main.__defaults__, build.main.__closure__)
    pipeline()


if __name__ == '__main__':
    main()
