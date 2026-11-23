"""Current releases survive cold caches only with exact independent review pins."""
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import preserve_current_releases as preserve
from editorial_gate import editorial_source_sha256


REPO = 'akshaymohan16/toxic-tales-library'
ORIGIN = 'https://akshaymohan16.github.io/toxic-tales-library/'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


class CurrentReleasePreservation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ('automation', 'quality', 'episodes', 'evidence', 'scripts'):
            (self.root / name).mkdir()
        self.config = {'allowed_repository': REPO, 'site_url': ORIGIN,
                       'production_entrypoint': 'scripts/build_current.py'}
        self.write('automation/config.json', self.config)
        (self.root / 'scripts/build_current.py').write_bytes(b'# fixture production entrypoint\n')
        self.releases = {}
        self.remote = {}
        self.episodes = {}
        self.manifests = {}
        self.downloads = []
        self.pipeline = SimpleNamespace(select_renderer=lambda episode: SimpleNamespace(VERSION='nature-motion-10.0'),
                                        render_fingerprint=self.fingerprint,
                                        release_ok=self.release_ok)
        self.patch('_load_pipeline', return_value=self.pipeline)
        self.patch('validate_pre_render', side_effect=editorial_source_sha256)
        self.download_mock = self.patch('_download', side_effect=self.download)
        env = patch.dict(os.environ, {'GITHUB_REPOSITORY': REPO})
        env.start()
        self.addCleanup(env.stop)
        self.add_episode('TT-008')

    def patch(self, name, **kwargs):
        patcher = patch.object(preserve, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encode(value))

    def fingerprint(self, path, evidence_path, renderer, source):
        return digest(Path(path).read_bytes() + Path(evidence_path).read_bytes() +
                      (self.root / 'scripts/build_current.py').read_bytes() + source.encode())

    @staticmethod
    def release_ok(release, manifest, episode):
        return (release.get('decision') == 'release'
                and all(release.get(key) == manifest.get(key)
                        for key in ('fingerprint', 'evidence_sha256', 'files'))
                and release.get('source_sha256') == manifest.get('editorial_source_sha256'))

    def download(self, relative, target, maximum):
        self.downloads.append(relative)
        data = self.remote[relative]
        if len(data) > maximum:
            raise ValueError('fixture download exceeds limit')
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def test_duplicate_released_source_cannot_bypass_fingerprint_preflight(self):
        self.write('episodes/unreviewed-alias.json', self.episodes['TT-008'])
        with self.assertRaisesRegex(ValueError, 'Duplicate or renamed'):
            preserve.preserve_current_releases(self.root)
        self.download_mock.assert_not_called()
        self.assertFalse((self.root / 'render-cache').exists())

    def add_episode(self, episode_id):
        stem = episode_id.lower()
        episode = {'id': episode_id, 'slug': stem + '-fixture', 'doi': '10.1000/' + stem,
                   'evidence_file': 'evidence/' + stem + '.md',
                   'production': {'renderer': 'nature-motion-10'},
                   'editorial_review': {'decision': 'pass'}}
        evidence = ('Full original evidence for ' + episode['doi'] + '\n').encode()
        (self.root / episode['evidence_file']).write_bytes(evidence)
        self.write('episodes/' + stem + '.json', episode)
        source_sha = editorial_source_sha256(episode, evidence.decode())
        fingerprint = self.fingerprint(self.root / ('episodes/' + stem + '.json'),
                                       self.root / episode['evidence_file'], None, source_sha)
        media_stem = episode['slug'] + '-' + fingerprint[:12]
        video = 'media/' + media_stem + '.mp4'
        cover = 'media/' + media_stem + '_cover.jpg'
        self.remote[video] = ('exact encoded bytes ' + stem).encode()
        self.remote[cover] = ('exact cover bytes ' + stem).encode()
        qa_frames = [stem + '-contact.jpg', stem + '-shot-01.jpg', stem + '-opening-0s.jpg',
                     stem + '-opening-1s.jpg', stem + '-final-frame.jpg',
                     stem + '-review-shot-01-plus-018.jpg', stem + '-review-shot-01-plus-070.jpg']
        for name in qa_frames:
            self.remote['qa/' + name] = ('exact encoded frame ' + name).encode()
        manifest = {'renderer': 'nature-motion-10.0', 'declared_renderer': 'nature-motion-10',
                    'fingerprint': fingerprint, 'evidence_sha256': digest(evidence),
                    'editorial_source_sha256': source_sha, 'technical_passed': True,
                    'files': {video: digest(self.remote[video]), cover: digest(self.remote[cover])},
                    'shots': [{'start': 0, 'end': 50}], 'duration': 50,
                    'contact_sheet': 'qa/' + stem + '-contact.jpg',
                    'boundary_frame_checks': ['qa/' + stem + suffix for suffix in
                                              ('-opening-0s.jpg', '-opening-1s.jpg', '-final-frame.jpg')]}
        manifest_path = 'qa/' + stem + '.json'
        self.remote[manifest_path] = encode(manifest)
        members = {Path(manifest_path).name: digest(self.remote[manifest_path]),
                   Path(cover).name: digest(self.remote[cover])}
        members.update({name: digest(self.remote['qa/' + name]) for name in qa_frames})
        index = {'schema_version': 1, 'episode_id': episode_id, 'fingerprint': fingerprint,
                 'video': {'path': video, 'sha256': digest(self.remote[video])},
                 'manifest': {'path': manifest_path, 'sha256': digest(self.remote[manifest_path])},
                 'source_episode_sha256': digest((self.root / ('episodes/' + stem + '.json')).read_bytes()),
                 'files': members,
                 'frames': [{'path': 'qa/' + name} for name in qa_frames]}
        index_path = 'qa/' + stem + '-review-index.json'
        self.remote[index_path] = encode(index)
        release = {'decision': 'release', 'fingerprint': fingerprint, 'files': manifest['files'],
                   'evidence_sha256': manifest['evidence_sha256'], 'source_sha256': source_sha,
                   'final_editorial_review': {'source_sha256': source_sha, 'decision': 'pass'},
                   'encoded_review_index_sha256': digest(self.remote[index_path])}
        self.releases[episode_id] = release
        self.write('quality/releases.json', self.releases)
        self.episodes[episode_id] = episode
        self.manifests[episode_id] = manifest
        return release

    def installed_files(self):
        return {path.relative_to(self.root / 'site').as_posix(): path.read_bytes()
                for path in (self.root / 'site').rglob('*') if path.is_file()}

    def test_cold_restore_installs_exact_bytes_and_warm_restore_needs_no_network(self):
        self.add_episode('TT-009')
        preserve.preserve_current_releases(self.root)
        installed = self.installed_files()
        for relative, data in self.remote.items():
            self.assertEqual(data, installed[relative], relative)
        cache = json.loads((self.root / 'render-cache/index.json').read_text())
        for episode_id, release in self.releases.items():
            self.assertEqual(release['fingerprint'], cache[episode_id])
        self.download_mock.reset_mock()
        preserve.preserve_current_releases(self.root)
        self.download_mock.assert_not_called()
        self.assertEqual(installed, self.installed_files())

    def test_every_source_is_validated_before_first_network_or_export_write(self):
        self.add_episode('TT-009')
        changed = dict(self.episodes['TT-009'], title='Changed story after review')
        self.write('episodes/tt-009.json', changed)
        with self.assertRaises((ValueError, AssertionError)):
            preserve.preserve_current_releases(self.root)
        self.download_mock.assert_not_called()
        self.assertEqual({}, self.installed_files())

    def test_changed_production_dependency_fails_before_network(self):
        (self.root / 'scripts/build_current.py').write_bytes(b'# altered renderer dependency\n')
        with self.assertRaises((ValueError, AssertionError)):
            preserve.preserve_current_releases(self.root)
        self.download_mock.assert_not_called()

    def test_remote_hash_mismatch_cannot_partially_install_a_release(self):
        self.add_episode('TT-009')
        video = next(path for path in self.manifests['TT-009']['files'] if path.endswith('.mp4'))
        self.remote[video] += b' corrupted'
        with self.assertRaises((ValueError, AssertionError)):
            preserve.preserve_current_releases(self.root)
        self.assertEqual({}, self.installed_files())

    def test_remote_manifest_mismatch_has_no_installation_effect(self):
        self.remote['qa/tt-008.json'] = encode(dict(self.manifests['TT-008'], fingerprint='b' * 64))
        with self.assertRaises((ValueError, AssertionError)):
            preserve.preserve_current_releases(self.root)
        self.assertEqual({}, self.installed_files())

    def test_unreleased_and_frozen_episodes_are_skipped(self):
        self.add_episode('TT-009')['decision'] = 'hold'
        self.releases['TT-007'] = {'decision': 'release'}
        self.write('episodes/tt-007.json', {'id': 'TT-007', 'production': {'renderer': 'old'}})
        self.write('quality/releases.json', self.releases)
        preserve.preserve_current_releases(self.root)
        self.assertFalse(any('tt-009' in path or 'tt-007' in path for path in self.downloads))
        self.assertFalse((self.root / 'site/qa/tt-009.json').exists())

    def test_missing_review_index_pin_fails_before_network(self):
        self.releases['TT-008'].pop('encoded_review_index_sha256')
        self.write('quality/releases.json', self.releases)
        with self.assertRaises((ValueError, AssertionError)):
            preserve.preserve_current_releases(self.root)
        self.download_mock.assert_not_called()

    def test_repo_origin_and_entrypoint_boundaries_fail_before_network(self):
        for key, value in (('allowed_repository', 'someone/else'),
                           ('site_url', 'https://example.com/archive/'),
                           ('production_entrypoint', '../build_current.py'),
                           ('production_entrypoint', 'scripts/other.py')):
            with self.subTest(key=key, value=value):
                config = dict(self.config, **{key: value})
                self.write('automation/config.json', config)
                with self.assertRaises((ValueError, AssertionError)):
                    preserve.preserve_current_releases(self.root)
        self.write('automation/config.json', self.config)
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'someone/else'}):
            with self.assertRaises((ValueError, AssertionError)):
                preserve.preserve_current_releases(self.root)
        self.download_mock.assert_not_called()

    def test_unsafe_release_paths_fail_before_network(self):
        self.releases['TT-008']['files']['../outside.mp4'] = 'a' * 64
        self.write('quality/releases.json', self.releases)
        with self.assertRaises((ValueError, AssertionError)):
            preserve.preserve_current_releases(self.root)
        self.download_mock.assert_not_called()


class Response:
    def __init__(self, data, url):
        self.stream = io.BytesIO(data)
        self.url = url
        self.headers = {'Content-Length': str(len(data))}

    def geturl(self):
        return self.url

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read(self, size=-1):
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.stream.close()


class CurrentDownloadBounds(unittest.TestCase):
    def test_allowed_download_is_exact_and_uses_only_expected_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'output.bin'
            with patch.object(preserve, '_open', return_value=Response(b'exact', ORIGIN + 'qa/tt-008.json')) as opened:
                preserve._download('qa/tt-008.json', target, 10)
            self.assertEqual(b'exact', target.read_bytes())
            request = opened.call_args.args[0]
            self.assertEqual(ORIGIN + 'qa/tt-008.json', request.full_url)

    def test_oversized_and_redirected_downloads_fail_closed(self):
        for data, url, maximum in ((b'x' * 20, ORIGIN + 'qa/tt-008.json', 10),
                                   (b'exact', 'https://example.com/qa/tt-008.json', 10)):
            with self.subTest(url=url, size=len(data)), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'output.bin'
                with patch.object(preserve, '_open', return_value=Response(data, url)):
                    with self.assertRaises((ValueError, AssertionError)):
                        preserve._download('qa/tt-008.json', target, maximum)

    def test_traversal_is_rejected_before_opening_network(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(preserve, '_open') as opened:
            with self.assertRaises((ValueError, AssertionError)):
                preserve._download('../outside', Path(directory) / 'output.bin', 10)
            opened.assert_not_called()


if __name__ == '__main__':
    unittest.main()
