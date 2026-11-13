"""Current scene dispatch, preserving every frozen motion-export fingerprint."""
import hashlib
import types

import build
import build_motion as frozen_motion
import production_archer as archer

ARCHER_DEPENDENCIES = ('scripts/production_archer.py', 'scripts/build_current.py')


def _is_archer(episode):
    return (episode or {}).get('production', {}).get('scene_family') == archer.FAMILY


def select_renderer(episode):
    if _is_archer(episode):
        if episode.get('id') in frozen_motion.FROZEN_LEGACY_EPISODES:
            raise ValueError('A frozen episode cannot adopt a new scene family')
        archer.validate_motion_spec(episode)
        return archer
    return frozen_motion.select_renderer(episode)


def render_fingerprint(path, evidence_path, renderer, editorial_source):
    if renderer is not archer:
        return frozen_motion.render_fingerprint(path, evidence_path, renderer, editorial_source)
    inherited = frozen_motion.render_fingerprint(path, evidence_path,
                                                 frozen_motion.motion_renderer, editorial_source)
    digest = hashlib.sha256(('archerfish-face-2016\0' + inherited).encode('ascii'))
    for relative in ARCHER_DEPENDENCIES:
        content = (build.ROOT / relative).read_bytes()
        digest.update(relative.encode('utf-8') + b'\0')
        digest.update(len(content).to_bytes(8, 'big'))
        digest.update(content)
    return digest.hexdigest()


def archer_motion_review_ok(release, manifest, episode):
    namespace = dict(frozen_motion.motion_review_ok.__globals__)
    namespace.update(validate_motion_spec=archer.validate_motion_spec, motion_renderer=archer)
    check = types.FunctionType(frozen_motion.motion_review_ok.__code__, namespace,
                               'check_archer_motion_review',
                               frozen_motion.motion_review_ok.__defaults__,
                               frozen_motion.motion_review_ok.__closure__)
    return check(release, manifest, episode)


def release_ok(release, manifest, episode=None):
    if not _is_archer(episode):
        if manifest.get('scene_family') == archer.FAMILY:
            return False
        return frozen_motion.release_ok(release, manifest, episode)
    if manifest.get('scene_family') != archer.FAMILY or manifest.get('scene_doi') != archer.DOI:
        return False
    namespace = dict(frozen_motion.release_ok.__globals__)
    namespace['motion_review_ok'] = archer_motion_review_ok
    check = types.FunctionType(frozen_motion.release_ok.__code__, namespace,
                               'check_archer_release', frozen_motion.release_ok.__defaults__,
                               frozen_motion.release_ok.__closure__)
    return check(release, manifest, episode)


def main():
    assert build.os.environ.get('GITHUB_REPOSITORY', build.REPO) == build.REPO, 'Repository boundary'
    preserved = frozen_motion.preserve_legacy_releases()
    print('Preserved exact legacy exports:', ', '.join(preserved['preserved_episodes']),
          '; restored files:', preserved['restored_files'])
    namespace = dict(build.main.__globals__)
    namespace.update(select_renderer=select_renderer, render_fingerprint=render_fingerprint,
                     release_ok=release_ok)
    pipeline = types.FunctionType(build.main.__code__, namespace, 'build_current_pipeline',
                                  build.main.__defaults__, build.main.__closure__)
    pipeline()


if __name__ == '__main__':
    main()
