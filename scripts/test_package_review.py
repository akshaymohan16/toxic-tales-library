"""Exact-media review bundling cannot copy videos or alter archived exports."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import package_review as review
import motion_spec


class ReviewPackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for folder in ('episodes', 'evidence', 'site/media', 'site/qa'):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        # Test-scoped evidence roots exercise the actual renderer selectors and
        # validators, then restore their globals immediately after each test.
        patcher = patch.object(motion_spec, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.create_fixture('TT-008', archer=True)
        (self.qa / 'tt-007.json').write_bytes(b'frozen release fixture')

    def create_fixture(self, episode_id, *, archer):
        self.episode_id = episode_id
        self.stem = episode_id.lower()
        doi = '10.1038/srep27523' if archer else '10.1000/example'
        evidence = 'Original paper evidence. DOI: ' + doi + '\n'
        evidence_path = self.root / ('evidence/' + self.stem + '.md')
        evidence_path.write_text(evidence, encoding='utf-8')
        self.ep = {'id': episode_id, 'doi': doi,
                   'slug': self.stem + '-fixture', 'evidence_file': 'evidence/' + self.stem + '.md',
                   'production': {'renderer': 'nature-motion-10', 'assets': [],
                       'motion': {'schema_version': 1, 'evidence_sha256': review.sha(evidence_path)},
                       'segments': [{'shots': [{'kind': 'archer_task' if archer else 'nature',
                                               'start': 0, 'end': 1}]}]}}
        if archer:
            self.ep['production']['scene_family'] = 'archerfish-face-2016'
        (self.root / ('episodes/' + self.stem + '.json')).write_text(json.dumps(self.ep), encoding='utf-8')
        self.video = self.root / ('site/media/' + self.stem + '-fixture-' + 'a' * 12 + '.mp4')
        self.video.write_bytes(b'exact original video bytes for hash binding')
        self.cover = self.video.with_name(self.video.stem + '_cover.jpg')
        Image.new('RGB', (1080, 1920), '#123456').save(self.cover)
        self.qa = self.root / 'site/qa'
        frame_names = [self.stem + suffix for suffix in ('-contact.jpg', '-shot-01.jpg', '-shot-02.jpg',
                       '-boundary-01-before.jpg', '-boundary-01-after.jpg',
                       '-opening-0s.jpg', '-opening-1s.jpg', '-final-frame.jpg')]
        for name in frame_names:
            Image.new('RGB', (540, 960), '#234567').save(self.qa / name)
        renderer = review.current.select_renderer(self.ep)
        self.manifest = {'renderer': renderer.VERSION, 'declared_renderer': renderer.DECLARED_RENDERER,
                         'motion': renderer.validate_motion_spec(self.ep),
                         'technical_passed': True, 'fingerprint': 'a' * 64,
                         'evidence_sha256': review.sha(evidence_path),
                         'editorial_source_sha256': review.editorial_source_sha256(self.ep, evidence),
                         'motion_spec_sha256': review.motion_spec_sha256(self.ep),
                         'files': {p.relative_to(self.root / 'site').as_posix(): review.sha(p)
                                   for p in (self.video, self.cover)},
                         'duration': 2., 'shots': [{'start': 0., 'end': 1.}, {'start': 1., 'end': 2.}],
                         'contact_sheet': 'qa/' + self.stem + '-contact.jpg',
                         'boundary_frame_checks': ['qa/' + n for n in frame_names[3:]]}
        if archer:
            self.manifest.update(scene_family='archerfish-face-2016', scene_doi=doi)
        self.write_manifest()

    def write_manifest(self):
        (self.qa / (self.stem + '.json')).write_text(json.dumps(self.manifest), encoding='utf-8')

    @staticmethod
    def extract(video, output, when):
        Image.new('RGB', (540, 960), '#345678').save(output)

    def test_bundle_binds_original_bytes_and_has_all_samples_but_no_video(self):
        original = {p: p.read_bytes() for p in (self.video, self.cover, self.qa / 'tt-007.json',
                                               self.qa / 'tt-008.json', self.qa / 'tt-008-shot-01.jpg')}
        with patch.object(review, 'extract_frame', side_effect=self.extract) as extract:
            result = review.package_review(self.root, 'TT-008')
        self.assertEqual([.18, .7, 1.18, 1.7], [call.args[2] for call in extract.call_args_list])
        self.assertEqual(12, result['frames'])
        archive = self.qa / 'tt-008-review.zip'
        with zipfile.ZipFile(archive) as bundle:
            self.assertFalse(any(name.endswith('.mp4') for name in bundle.namelist()))
            index = json.loads(bundle.read('review-index.json'))
            self.assertEqual(review.sha(self.video), index['video']['sha256'])
            for name, digest in index['files'].items():
                import hashlib
                self.assertEqual(digest, hashlib.sha256(bundle.read(name)).hexdigest())
            self.assertIn('tt-008-review-shot-02-plus-070.jpg', bundle.namelist())
        for path, before in original.items():
            self.assertEqual(before, path.read_bytes())
        page = (self.qa / 'tt-008-review.html').read_text(encoding='utf-8')
        self.assertIn('Download review ZIP', page)
        self.assertIn('../media/' + self.video.name, page)
        self.assertIn('does not grant publication approval', page)
        first_archive = archive.read_bytes()
        with patch.object(review, 'extract_frame', side_effect=self.extract):
            review.package_review(self.root, 'TT-008')
        self.assertEqual(first_archive, archive.read_bytes())

    def test_altered_video_fails_before_extraction(self):
        self.video.write_bytes(b'changed')
        with patch.object(review, 'extract_frame') as extract:
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                review.package_review(self.root, 'TT-008')
        extract.assert_not_called()
        self.assertFalse((self.qa / 'tt-008-review.zip').exists())

    def test_traversal_and_historical_episode_fail_before_extraction(self):
        self.manifest['files']['../outside.mp4'] = 'a' * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            review.package_review(self.root, 'TT-008')
        with self.assertRaisesRegex(ValueError, 'scoped'):
            review.package_review(self.root, 'TT-007')
        with self.assertRaisesRegex(ValueError, 'scoped'):
            review.review_output(self.qa, 'tt-007.json', 'TT-008')

    def test_current_packages_archer_and_ordinary_motion_and_skips_frozen_and_nonproduction(self):
        self.create_fixture('TT-009', archer=False)
        for episode in ({'id': 'TT-001'}, {'id': 'TT-007', 'production': {'renderer': 'old'}}):
            (self.root / ('episodes/' + episode['id'].lower() + '.json')).write_text(json.dumps(episode))
        before = (self.qa / 'tt-007.json').read_bytes()
        with patch.object(review, 'extract_frame', side_effect=self.extract):
            results = review.package_current(self.root)
        self.assertEqual(['TT-008', 'TT-009'], [result['episode'] for result in results])
        self.assertEqual(before, (self.qa / 'tt-007.json').read_bytes())
        self.assertFalse((self.qa / 'tt-007-review.zip').exists())
        with zipfile.ZipFile(self.qa / 'tt-009-review.zip') as bundle:
            index = json.loads(bundle.read('review-index.json'))
            self.assertEqual('TT-009', index['episode_id'])
            self.assertTrue(all(frame['path'].startswith('qa/tt-009-') for frame in index['frames']))
        self.assertIn('TT-009 encoded export review', (self.qa / 'tt-009-review.html').read_text())

    def test_unknown_renderer_and_mismatched_actual_receipt_fail_closed(self):
        self.create_fixture('TT-009', archer=False)
        self.ep['production']['renderer'] = 'unknown-renderer'
        (self.root / 'episodes/tt-009.json').write_text(json.dumps(self.ep))
        with self.assertRaisesRegex(ValueError, 'require nature-motion-10'):
            review.package_review(self.root, 'TT-009')
        self.ep['production']['renderer'] = 'nature-motion-10'
        (self.root / 'episodes/tt-009.json').write_text(json.dumps(self.ep))
        self.manifest['motion']['spec_sha256'] = 'b' * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'identities'):
            review.package_review(self.root, 'TT-009')

    def test_dynamic_scope_cannot_write_other_episode_or_escape(self):
        for episode_id in ('TT-007', '../TT-009', 'tt-009', 'TT-009/extra'):
            with self.subTest(episode_id=episode_id), self.assertRaises(ValueError):
                review.package_review(self.root, episode_id)
        for name in ('tt-008-review.zip', '../tt-009-review.zip', 'tt-009.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                review.review_output(self.qa, name, 'TT-009')
        self.assertEqual(self.qa / 'tt-009-review.zip',
                         review.review_output(self.qa, 'tt-009-review.zip', 'TT-009'))

    def test_released_package_retains_index_bytes_without_extracting_or_rewriting(self):
        (self.root / 'quality').mkdir()
        (self.root / 'quality/releases.json').write_text(json.dumps({'TT-008': {'decision': 'release'}}))
        index = self.qa / 'tt-008-review-index.json'
        index.write_bytes(b'exact independently reviewed index bytes\n')
        original = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        with patch.object(review.preserve_current, 'verify_released_local', return_value={'verified': True}) as verify:
            with patch.object(review, 'extract_frame') as extract:
                direct = review.package_review(self.root, 'TT-008')
                current = review.package_current(self.root)
        self.assertIn('retained', direct['status'])
        self.assertIn('retained', current[0]['status'])
        self.assertEqual(2, verify.call_count)
        verify.assert_called_with(self.root, 'TT-008')
        extract.assert_not_called()
        self.assertEqual(original, {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

    def test_missing_or_changed_released_local_pins_block_without_regeneration(self):
        (self.root / 'quality').mkdir()
        (self.root / 'quality/releases.json').write_text(json.dumps({'TT-008': {'decision': 'release'}}))
        (self.qa / 'tt-008.json').unlink()
        with patch.object(review.preserve_current, 'verify_released_local', side_effect=ValueError('Missing pinned local bytes')):
            with patch.object(review, 'extract_frame') as extract:
                with self.assertRaisesRegex(ValueError, 'pinned'):
                    review.package_current(self.root)
        extract.assert_not_called()

    def test_short_shot_samples_remain_inside_the_shot(self):
        self.manifest['shots'] = [{'start': 0., 'end': .1}, {'start': .1, 'end': 2.}]
        self.write_manifest()
        with patch.object(review, 'extract_frame', side_effect=self.extract) as extract:
            review.package_review(self.root, 'TT-008')
        self.assertTrue(all(0 <= call.args[2] < .1 for call in extract.call_args_list[:2]))

    def test_ffmpeg_samples_original_encoded_video_at_native_phone_ratio(self):
        with patch.object(review.subprocess, 'run') as run:
            review.extract_frame(self.video, self.qa / 'new.jpg', 1.18)
        command = run.call_args.args[0]
        self.assertEqual('1.180000', command[command.index('-ss') + 1])
        self.assertEqual(str(self.video), command[command.index('-i') + 1])
        self.assertEqual('scale=540:960', command[command.index('-vf') + 1])


if __name__ == '__main__':
    unittest.main()
