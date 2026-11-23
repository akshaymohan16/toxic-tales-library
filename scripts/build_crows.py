"""Additive TT-010 scene dispatch. Preserve all TT-002..TT-009 releases unchanged."""
import hashlib
import types
import build
import build_next as previous
import production_crows as crow

CROW_DEPENDENCIES = ('scripts/production_crows.py', 'scripts/build_crows.py')


def select_renderer(episode):
    if (episode or {}).get('production', {}).get('scene_family') == crow.FAMILY:
        if episode.get('id') != 'TT-010' or episode.get('doi') != crow.DOI:
            raise ValueError('Crow renderer is restricted to the focal experiment')
        crow.validate_motion_spec(episode)
        return crow
    return previous.select_renderer(episode)


def render_fingerprint(path, evidence_path, renderer, editorial_source):
    if renderer is not crow:
        return previous.render_fingerprint(path, evidence_path, renderer, editorial_source)
    inherited = previous.previous.frozen_motion.render_fingerprint(
        path, evidence_path, previous.previous.frozen_motion.motion_renderer,
        editorial_source)
    digest = hashlib.sha256(('corvus-water-2014\\0' + inherited).encode('ascii'))
    for relative in CROW_DEPENDENCIES:
        content = (build.ROOT / relative).read_bytes()
        digest.update(relative.encode('utf-8') + b'\\0')
        digest.update(len(content).to_bytes(8, 'big'))
        digest.update(content)
    return digest.hexdigest()


def _crow_motion_review_ok(release, manifest, episode):
    namespace = dict(previous.previous.frozen_motion.motion_review_ok.__globals__)
    namespace.update(validate_motion_spec=crow.validate_motion_spec,
                     motion_renderer=crow)
    checker = types.FunctionType(
        previous.previous.frozen_motion.motion_review_ok.__code__, namespace,
        'check_crow_motion_review',
        previous.previous.frozen_motion.motion_review_ok.__defaults__,
        previous.previous.frozen_motion.motion_review_ok.__closure__)
    return checker(release, manifest, episode)


def release_ok(release, manifest, episode=None):
    if not episode or episode.get('production', {}).get('scene_family') != crow.FAMILY:
        if manifest.get('scene_family') == crow.FAMILY:
            return False
        return previous.release_ok(release, manifest, episode)
    if (manifest.get('scene_family') != crow.FAMILY or
            manifest.get('scene_doi') != crow.DOI):
        return False
    namespace = dict(previous.previous.frozen_motion.release_ok.__globals__)
    namespace['motion_review_ok'] = _crow_motion_review_ok
    checker = types.FunctionType(
        previous.previous.frozen_motion.release_ok.__code__, namespace,
        'check_crow_release', previous.previous.frozen_motion.release_ok.__defaults__,
        previous.previous.frozen_motion.release_ok.__closure__)
    return checker(release, manifest, episode)


def main():
    assert build.os.environ.get('GITHUB_REPOSITORY', build.REPO) == build.REPO
    preserved = previous.previous.frozen_motion.preserve_legacy_releases()
    print('Preserved frozen TT-002..TT-009 releases:',
          ', '.join(preserved['preserved_episodes']))
    namespace = dict(build.main.__globals__)
    namespace.update(select_renderer=select_renderer,
                     render_fingerprint=render_fingerprint, release_ok=release_ok)
    pipeline = types.FunctionType(build.main.__code__, namespace,
                                  'build_crows_pipeline',
                                  build.main.__defaults__, build.main.__closure__)
    pipeline()


if __name__ == '__main__':
    main()
