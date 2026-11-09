"""No renderer may regenerate an existing export when the cache is cold."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

import preserve_releases as preserve


class PreserveReleases(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fp, self.source = 'a' * 64, 'b' * 64
        self.media = b'exact reviewed video bytes'
        self.evidence = b'Verified original evidence'
        self.save('episodes/tt-006.json', {'id': 'TT-006', 'evidence_file': 'evidence/tt-006.md',
                                        'production': {'renderer': 'nature-branded-9'}})
        evidence = self.root / 'evidence/tt-006.md'
        evidence.parent.mkdir()
        evidence.write_bytes(self.evidence)
        self.release = {'decision': 'release', 'fingerprint': self.fp,
                        'evidence_sha256': hashlib.sha256(self.evidence).hexdigest(),
                        'files': {'media/old.mp4': hashlib.sha256(self.media).hexdigest()}}
        self.frozen = {'TT-006': ('nature-branded-9', self.fp, preserve._release_identity(self.release))}
        patch.object(preserve, 'FROZEN_LEGACY', self.frozen).start()
        self.save('quality/releases.json', {'TT-006': self.release})
        self.manifest = {**self.release, 'renderer': 'nature-branded-9.0',
                         'editorial_source_sha256': self.source}
        self.remote = {'qa/tt-006.json': json.dumps(self.manifest).encode(),
                       'media/old.mp4': self.media}
        for name, value in (('validate_pre_render', self.source),):
            patcher = patch.object(preserve, name, return_value=value)
            patcher.start(); self.addCleanup(patcher.stop)
        self.fingerprint = patch.object(preserve.build, 'render_fingerprint', return_value=self.fp).start()
        self.addCleanup(patch.stopall)
        patch.object(preserve.build, 'select_renderer',
                     return_value=SimpleNamespace(VERSION='nature-branded-9.0')).start()

    def save(self, name, value):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding='utf-8')

    def download(self, name, target, maximum):
        target.write_bytes(self.remote[name])

    def reject_without_writes(self, message):
        with patch.object(preserve, '_download') as download:
            with self.assertRaisesRegex(ValueError, message):
                preserve.preserve_legacy_releases(self.root)
            download.assert_not_called()
        self.assertFalse((self.root / 'render-cache').exists())
        self.assertFalse((self.root / 'site').exists())

    def test_frozen_episode_cannot_convert_to_motion_or_lose_production(self):
        path = self.root / 'episodes/tt-006.json'
        episode = json.loads(path.read_text())
        for production in ({'renderer': 'nature-motion-10'}, {'renderer': 'nature-story-8'}, None):
            changed = {**episode, 'production': production}
            self.save('episodes/tt-006.json', changed)
            with self.subTest(production=production):
                self.reject_without_writes('Frozen legacy renderer changed')

    def test_missing_renamed_relabelled_and_duplicate_frozen_ids_are_rejected(self):
        path = self.root / 'episodes/tt-006.json'
        episode = json.loads(path.read_text())
        path.unlink()
        self.reject_without_writes('Missing frozen legacy episode')
        self.save('episodes/renamed.json', episode)
        self.reject_without_writes('Renamed frozen legacy episode')
        self.save('episodes/tt-006.json', episode)
        self.reject_without_writes('Duplicate production episode identity')
        (self.root / 'episodes/renamed.json').unlink()
        self.save('episodes/tt-006.json', {**episode, 'id': 'TT-008'})
        self.reject_without_writes('Missing frozen legacy episode')

    def test_mutating_source_release_and_qa_together_cannot_replace_frozen_identity(self):
        for key, replacement in (('fingerprint', 'c' * 64), ('evidence_sha256', 'c' * 64),
                                 ('files', {'media/replacement.mp4': 'c' * 64})):
            changed = {**self.release, key: replacement}
            self.save('quality/releases.json', {'TT-006': changed})
            self.save('site/qa/tt-006.json', {**self.manifest, key: replacement})
            self.fingerprint.return_value = changed['fingerprint']
            before = (self.root / 'site/qa/tt-006.json').read_bytes()
            with self.subTest(field=key), patch.object(preserve, '_download') as download:
                with self.assertRaisesRegex(ValueError, 'Pinned legacy release identity changed'):
                    preserve.preserve_legacy_releases(self.root)
                download.assert_not_called()
            self.assertFalse((self.root / 'render-cache').exists())
            self.assertEqual((self.root / 'site/qa/tt-006.json').read_bytes(), before)

    def test_all_frozen_sources_validate_before_first_archive_download(self):
        self.frozen['TT-007'] = self.frozen['TT-006']
        self.save('quality/releases.json', {'TT-006': self.release, 'TT-007': self.release})
        self.save('episodes/tt-007.json', {'id': 'TT-007', 'evidence_file': 'evidence/tt-006.md',
                                        'production': {'renderer': 'nature-branded-9'}})
        self.fingerprint.side_effect = lambda path, *args: self.fp if path.stem == 'tt-006' else 'c' * 64
        self.reject_without_writes('Legacy source changed')

    def test_new_motion_episode_is_not_treated_as_a_historical_export(self):
        self.save('episodes/tt-008.json', {'id': 'TT-008', 'evidence_file': 'evidence/future.md',
                                        'production': {'renderer': 'nature-motion-10'}})
        with patch.object(preserve, '_download', side_effect=self.download):
            self.assertEqual(preserve.preserve_legacy_releases(self.root),
                             {'preserved_episodes': ['TT-006'], 'restored_files': 2})
        self.fingerprint.assert_called_once()

    def test_cold_restore_exact_bytes_then_warm_cache_needs_no_network(self):
        release_bytes = (self.root / 'quality/releases.json').read_bytes()
        with patch.object(preserve, '_download', side_effect=self.download) as download:
            result = preserve.preserve_legacy_releases(self.root)
            self.assertEqual(result, {'preserved_episodes': ['TT-006'], 'restored_files': 2})
            self.assertEqual(download.call_count, 2)
        self.assertEqual((self.root / 'site/media/old.mp4').read_bytes(), self.media)
        self.assertEqual(json.loads((self.root / 'render-cache/index.json').read_text()), {'TT-006': self.fp})
        self.assertEqual((self.root / 'quality/releases.json').read_bytes(), release_bytes)
        with patch.object(preserve, '_download', side_effect=AssertionError('unexpected network')):
            self.assertEqual(preserve.preserve_legacy_releases(self.root)['restored_files'], 0)

    def test_missing_or_changed_sources_never_download_or_render(self):
        with patch.object(preserve, '_download', side_effect=AssertionError('unexpected network')):
            self.fingerprint.return_value = 'c' * 64
            with self.assertRaisesRegex(ValueError, 'Legacy source changed'):
                preserve.preserve_legacy_releases(self.root)
            self.fingerprint.return_value = self.fp
            (self.root / 'evidence/tt-006.md').write_bytes(b'new evidence')
            with self.assertRaisesRegex(ValueError, 'Legacy source changed'):
                preserve.preserve_legacy_releases(self.root)
            (self.root / 'evidence/tt-006.md').unlink()
            with self.assertRaises(FileNotFoundError):
                preserve.preserve_legacy_releases(self.root)
        self.assertFalse((self.root / 'render-cache/index.json').exists())

    def test_unknown_release_and_mismatched_remote_bytes_fail_before_install(self):
        self.remote['media/old.mp4'] = b'different encoded bytes'
        with patch.object(preserve, '_download', side_effect=self.download):
            with self.assertRaisesRegex(ValueError, 'media hash mismatch'):
                preserve.preserve_legacy_releases(self.root)
        self.assertFalse((self.root / 'site/qa/tt-006.json').exists())
        self.assertFalse((self.root / 'site/media/old.mp4').exists())
        self.assertFalse((self.root / 'render-cache/index.json').exists())
        self.save('quality/releases.json', {})
        with self.assertRaisesRegex(ValueError, 'No exact legacy release'):
            preserve.preserve_legacy_releases(self.root)

    def test_remote_qa_must_match_full_release_and_source_identity(self):
        for key in ('files', 'fingerprint', 'evidence_sha256', 'editorial_source_sha256', 'renderer'):
            self.remote['qa/tt-006.json'] = json.dumps({**self.manifest, key: 'stale'}).encode()
            with self.subTest(field=key), patch.object(preserve, '_download', side_effect=self.download):
                with self.assertRaisesRegex(ValueError, 'QA identity mismatch'):
                    preserve.preserve_legacy_releases(self.root)
            self.assertFalse((self.root / 'render-cache/index.json').exists())

    def test_held_and_rejected_exports_remain_held_and_rejected(self):
        for decision in ('hold_legacy_carousel_review', 'rejected_by_owner'):
            self.save('quality/releases.json', {'TT-006': {**self.release, 'decision': decision}})
            with patch.object(preserve, '_download', side_effect=self.download):
                preserve.preserve_legacy_releases(self.root)
            self.assertEqual(json.loads((self.root / 'quality/releases.json').read_text())['TT-006']['decision'], decision)

    def test_publication_receipts_and_review_status_are_outside_the_media_identity_pin(self):
        changed = copy.deepcopy(self.release)
        changed.update(publication_receipt={'provider_id': 'existing-post'},
                       visual_review={'decision': 'hold', 'finding': 'Existing review retained'})
        self.save('quality/releases.json', {'TT-006': changed})
        with patch.object(preserve, '_download', side_effect=self.download):
            preserve.preserve_legacy_releases(self.root)
        self.assertEqual(json.loads((self.root / 'quality/releases.json').read_text())['TT-006'], changed)

    def test_unsafe_paths_and_external_redirects_are_rejected(self):
        for path in ('../media/a.mp4', 'media/../a.mp4', 'media\\a.mp4',
                     'https://example.org/a.mp4', 'media/a.mp4?download=1'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                preserve._safe_path(self.root, path, 'media')
        with self.assertRaisesRegex(ValueError, 'redirects are refused'):
            preserve._NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.org/file')
        response = io.BytesIO(b'data')
        response.geturl = lambda: 'https://example.org/file'
        with patch.object(preserve, '_open', return_value=response):
            with self.assertRaisesRegex(ValueError, 'authorised Pages origin'):
                preserve._download('media/a.mp4', self.root / 'download', 10)

    def test_download_is_size_bounded_and_uses_only_authorised_origin(self):
        response = io.BytesIO(b'too large')
        response.geturl = lambda: preserve.SITE_URL + 'media/a.mp4'
        with patch.object(preserve, '_open', return_value=response) as opened:
            with self.assertRaisesRegex(ValueError, 'size limit'):
                preserve._download('media/a.mp4', self.root / 'download', 4)
            self.assertEqual(opened.call_args.args[0].full_url, preserve.SITE_URL + 'media/a.mp4')

    def test_referenced_qa_restores_with_separate_observed_hash_receipt(self):
        jpeg = io.BytesIO()
        Image.new('RGB', (100, 160), '#123456').save(jpeg, 'JPEG')
        self.manifest.update(contact_sheet='qa/tt-006-contact.jpg',
                             boundary_frame_checks=['qa/tt-006-opening-0s.jpg'])
        self.remote['qa/tt-006.json'] = json.dumps(self.manifest).encode()
        for name in ('qa/tt-006-contact.jpg', 'qa/tt-006-opening-0s.jpg'):
            self.remote[name] = jpeg.getvalue()
        with patch.object(preserve, '_download', side_effect=self.download):
            self.assertEqual(preserve.preserve_legacy_releases(self.root)['restored_files'], 4)
        receipt = json.loads((self.root / 'render-cache/legacy-qa-observations.json').read_text())
        self.assertEqual(len(receipt), 2)
        self.assertFalse(receipt['qa/tt-006-contact.jpg']['historical_release_hash_verified'])
        self.assertEqual(receipt['qa/tt-006-contact.jpg']['sha256'], hashlib.sha256(jpeg.getvalue()).hexdigest())
        with patch.object(preserve, '_download', side_effect=AssertionError('unexpected network')):
            self.assertEqual(preserve.preserve_legacy_releases(self.root)['restored_files'], 0)

    def test_missing_corrupt_or_malicious_ancillary_qa_blocks_all_installation(self):
        for name, data in (('qa/tt-006-missing.jpg', None),
                           ('qa/tt-006-invalid.jpg', b'not a jpeg'),
                           ('qa/../outside.jpg', b'not a jpeg'),
                           ('qa/tt-007-contact.jpg', b'not a jpeg')):
            self.manifest['contact_sheet'] = name
            self.remote['qa/tt-006.json'] = json.dumps(self.manifest).encode()
            if data is not None:
                self.remote[name] = data
            with self.subTest(path=name), patch.object(preserve, '_download', side_effect=self.download):
                with self.assertRaises((ValueError, KeyError, OSError)):
                    preserve.preserve_legacy_releases(self.root)
            self.assertFalse((self.root / 'site/media/old.mp4').exists())
            self.assertFalse((self.root / 'render-cache/index.json').exists())


class RealProductionHistory(unittest.TestCase):
    def test_all_six_historical_sources_and_media_identities_match_pins(self):
        self.assertEqual(set(preserve.FROZEN_LEGACY), {f'TT-{number:03d}' for number in range(2, 8)})
        original = Path.read_bytes
        with patch.object(Path, 'read_bytes', lambda path: original(path).replace(b'\r\n', b'\n')):
            releases = preserve.build.read(preserve.build.ROOT / 'quality/releases.json')
            verified = preserve._verified_legacy_sources(preserve.build.ROOT, releases)
        self.assertEqual([entry[0] for entry in verified], sorted(preserve.FROZEN_LEGACY))

    def test_frozen_approved_story_still_supports_standalone_nonpublishing_preview(self):
        import preview_motion
        original = Path.read_bytes
        with tempfile.TemporaryDirectory() as temporary, patch.object(
                Path, 'read_bytes', lambda path: original(path).replace(b'\r\n', b'\n')):
            episode, output, source, fingerprint = preview_motion.prepare(
                preserve.build.ROOT / 'quality/motion-preview/tt-007.json', Path(temporary) / 'preview')
            self.assertEqual(episode['id'], 'TT-007')
            self.assertEqual(episode['production']['renderer'], 'nature-motion-10')
            self.assertIs(episode['publication_enabled'], False)
            self.assertEqual(episode['posts'], [])
            self.assertEqual(fingerprint, preserve.FROZEN_LEGACY['TT-007'][1])
            self.assertTrue(source)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
