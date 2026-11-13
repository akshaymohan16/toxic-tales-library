"""Exact-media review bundling cannot copy videos or alter archived exports."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import package_review as review


class ReviewPackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for folder in ('episodes', 'evidence', 'site/media', 'site/qa'):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.ep = {'id': 'TT-008', 'doi': '10.1038/srep27523',
                   'slug': 'tt-008-fixture', 'evidence_file': 'evidence/tt-008.md',
                   'production': {'scene_family': 'archerfish-face-2016'}}
        (self.root / 'evidence/tt-008.md').write_text('Original paper evidence.\n', encoding='utf-8')
        (self.root / 'episodes/tt-008.json').write_text(json.dumps(self.ep), encoding='utf-8')
        self.video = self.root / ('site/media/tt-008-fixture-' + 'a' * 12 + '.mp4')
        self.video.write_bytes(b'exact original video bytes for hash binding')
        self.cover = self.video.with_name(self.video.stem + '_cover.jpg')
        Image.new('RGB', (1080, 1920), '#123456').save(self.cover)
        self.qa = self.root / 'site/qa'
        frame_names = ['tt-008-contact.jpg', 'tt-008-shot-01.jpg', 'tt-008-shot-02.jpg',
                       'tt-008-boundary-01-before.jpg', 'tt-008-boundary-01-after.jpg',
                       'tt-008-opening-0s.jpg', 'tt-008-opening-1s.jpg', 'tt-008-final-frame.jpg']
        for name in frame_names:
            Image.new('RGB', (540, 960), '#234567').save(self.qa / name)
        self.manifest = {'scene_family': 'archerfish-face-2016', 'scene_doi': self.ep['doi'],
                         'technical_passed': True, 'fingerprint': 'a' * 64,
                         'evidence_sha256': review.sha(self.root / 'evidence/tt-008.md'),
                         'editorial_source_sha256': review.editorial_source_sha256(self.ep, 'Original paper evidence.\n'),
                         'motion_spec_sha256': review.motion_spec_sha256(self.ep),
                         'files': {p.relative_to(self.root / 'site').as_posix(): review.sha(p)
                                   for p in (self.video, self.cover)},
                         'duration': 2., 'shots': [{'start': 0., 'end': 1.}, {'start': 1., 'end': 2.}],
                         'contact_sheet': 'qa/tt-008-contact.jpg',
                         'boundary_frame_checks': ['qa/' + n for n in frame_names[3:]]}
        self.write_manifest()
        (self.qa / 'tt-007.json').write_bytes(b'frozen release fixture')

    def write_manifest(self):
        (self.qa / 'tt-008.json').write_text(json.dumps(self.manifest), encoding='utf-8')

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
            review.review_output(self.qa, 'tt-007.json')

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
