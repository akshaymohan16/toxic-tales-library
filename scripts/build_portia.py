"""Additive TT-011 scene dispatch. Preserve all TT-002..TT-010 releases unchanged."""
import hashlib
import types
import build
import build_crows as previous
import production_portia as portia

PORTIA_DEPENDENCIES = ('scripts/production_portia.py', 'scripts/build_portia.py')


def select_renderer(episode):
    if (episode or {}).get('production', {}).get('scene_family') == portia.FAMILY:
        if episode.get('id') != 'TT-011' or episode.get('doi') != portia.DOI:
            raise ValueError('Portia renderer is restricted to the focal experiment')
        portia.validate_motion_spec(episode)
        return portia
    return previous.select_renderer(episode)


def render_fingerprint(path, evidence_path, renderer, editorial_source):
    if renderer is not portia:
        return previous.render_fingerprint(path, evidence_path, renderer, editorial_source)
    inherited = previous.previous.previous.frozen_motion.render_fingerprint(
        path, evidence_path, previous.previous.previous.frozen_motion.motion_renderer,
        editorial_source)
    digest = hashlib.sha256(('portia-sleep-2026\\0' + inherited).encode('ascii'))
    for relative in PORTIA_DEPENDENCIES:
        content = (build.ROOT / relative).read_bytes()
        digest.update(relative.encode('utf-8') + b'\\0')
        digest.update(len(content).to_bytes(8, 'big'))
        digest.update(content)
    return digest.hexdigest()


def _portia_motion_review_ok(release, manifest, episode):
    namespace = dict(previous.previous.previous.frozen_motion.motion_review_ok.__globals__)
    namespace.update(validate_motion_spec=portia.validate_motion_spec,
                     motion_renderer=portia)
    checker = types.FunctionType(
        previous.previous.previous.frozen_motion.motion_review_ok.__code__, namespace,
        'check_portia_motion_review',
        previous.previous.previous.frozen_motion.motion_review_ok.__defaults__,
        previous.previous.previous.frozen_motion.motion_review_ok.__closure__)
    return checker(release, manifest, episode)


def release_ok(release, manifest, episode=None):
    if not episode or episode.get('production', {}).get('scene_family') != portia.FAMILY:
        if manifest.get('scene_family') == portia.FAMILY:
            return False
        return previous.release_ok(release, manifest, episode)
    if (manifest.get('scene_family') != portia.FAMILY or
            manifest.get('scene_doi') != portia.DOI):
        return False
    namespace = dict(previous.previous.previous.frozen_motion.release_ok.__globals__)
    namespace['motion_review_ok'] = _portia_motion_review_ok
    checker = types.FunctionType(
        previous.previous.previous.frozen_motion.release_ok.__code__, namespace,
        'check_portia_release', previous.previous.previous.frozen_motion.release_ok.__defaults__,
        previous.previous.previous.frozen_motion.release_ok.__closure__)
    return checker(release, manifest, episode)


def main():
    assert build.os.environ.get('GITHUB_REPOSITORY', build.REPO) == build.REPO
    preserved = previous.previous.previous.frozen_motion.preserve_legacy_releases()
    print('Preserved frozen TT-002..TT-010 releases:',
          ', '.join(preserved['preserved_episodes']))
    namespace = dict(build.main.__globals__)
    namespace.update(select_renderer=select_renderer,
                     render_fingerprint=render_fingerprint, release_ok=release_ok)
    pipeline = types.FunctionType(build.main.__code__, namespace,
                                  'build_portias_pipeline',
                                  build.main.__defaults__, build.main.__closure__)
    pipeline()


if __name__ == '__main__':
    main()
