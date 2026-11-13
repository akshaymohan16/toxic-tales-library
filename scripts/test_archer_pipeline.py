"""Source-binding, non-mutating dispatch and picture checks for new archer art."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import build
import build_current as current
import build_motion as frozen
import motion_spec
import production_archer as archer
from editorial_gate import validate_pre_render
from test_motion import FixtureTypography


class ArcherPipeline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'evidence').mkdir()
        evidence = ('Focal DOI: ' + archer.DOI + '\nTask illustration, no numerical result.\n').encode()
        (self.root / 'evidence/fixture.md').write_bytes(evidence)
        self.ep = {'id': 'TT-008', 'doi': archer.DOI, 'evidence_file': 'evidence/fixture.md',
                   'evidence': {'claims': []}, 'production': {
                       'renderer': archer.DECLARED_RENDERER, 'scene_family': archer.FAMILY,
                       'assets': [], 'motion': {'schema_version': 1,
                           'evidence_sha256': hashlib.sha256(evidence).hexdigest()},
                       'segments': [{'speech': 'A fish makes a learned choice.',
                           'captions': ['A fish makes a learned choice.'],
                           'shots': [{'kind': 'archer_task', 'start': 0, 'end': 1}]}]}}
        patcher = patch.object(motion_spec, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_extended_scene_receipt_hashes_actual_unmodified_plan(self):
        before = copy.deepcopy(self.ep)
        receipt = archer.validate_motion_spec(self.ep)
        self.assertEqual(self.ep, before)
        self.assertEqual(receipt['spec_sha256'], motion_spec.motion_spec_sha256(self.ep))
        self.assertEqual(receipt['scene_doi'], archer.DOI)
        self.assertEqual(receipt['metrics'], [])

    def test_wrong_doi_and_unbound_kinds_fail_closed(self):
        wrong = copy.deepcopy(self.ep)
        wrong['doi'] = '10.0000/wrong'
        with self.assertRaises(ValueError):
            archer.validate_motion_spec(wrong)
        self.ep['production']['segments'][0]['shots'][0]['kind'] = 'made_up_scene'
        with self.assertRaises(ValueError):
            archer.validate_motion_spec(self.ep)

    def test_diagrams_cannot_smuggle_unverified_numerical_metrics(self):
        self.ep['production']['segments'][0]['shots'][0]['motion'] = {'metric': {'value': 99}}
        with self.assertRaisesRegex(ValueError, 'numerical'):
            archer.validate_motion_spec(self.ep)

    def test_frozen_episode_cannot_switch_to_archer_family(self):
        self.ep['id'] = 'TT-007'
        with self.assertRaisesRegex(ValueError, 'frozen'):
            current.select_renderer(self.ep)

    def test_current_wrapper_keeps_real_motion_fingerprints_unchanged(self):
        for eid in ('tt-006', 'tt-007'):
            path = build.ROOT / 'episodes' / (eid + '.json')
            episode = json.loads(path.read_text(encoding='utf-8'))
            evidence = build.ROOT / episode['evidence_file']
            source_hash = validate_pre_render(episode, evidence.read_text(encoding='utf-8'))
            with patch.object(motion_spec, 'ROOT', build.ROOT):
                old_renderer = frozen.select_renderer(episode)
                self.assertIs(current.select_renderer(episode), old_renderer)
            self.assertEqual(current.render_fingerprint(path, evidence, old_renderer, source_hash),
                             frozen.render_fingerprint(path, evidence, old_renderer, source_hash))

    def test_new_fingerprint_binds_new_renderer_and_wrapper_bytes(self):
        with patch.object(frozen, 'render_fingerprint', return_value='a' * 64):
            one = current.render_fingerprint('ep', 'evidence', archer, 'source')
            original = Path.read_bytes
            with patch.object(Path, 'read_bytes', lambda path: original(path) +
                              (b'# changed' if path.name == 'production_archer.py' else b'')):
                two = current.render_fingerprint('ep', 'evidence', archer, 'source')
        self.assertNotEqual(one, two)

    def test_all_scenes_render_native_dimensions_without_network(self):
        visual = archer.Visuals.__new__(archer.Visuals)
        visual.ep = self.ep
        visual.type = FixtureTypography()
        visual.background = Image.new('RGB', (1080, 1920), '#071c22')
        for kind in archer.SCENES:
            with self.subTest(kind=kind):
                early = visual.diagram(kind, .5, .1)
                late = visual.diagram(kind, 2., .4)
                self.assertEqual((1080, 1920), early.size)
                self.assertEqual('RGB', early.mode)
                self.assertNotEqual(early.tobytes(), late.tobytes())

    def test_missing_or_mismatched_scene_manifest_is_not_released(self):
        self.assertFalse(current.release_ok({}, {}, self.ep))
        self.assertFalse(current.release_ok({}, {'scene_family': archer.FAMILY}, {}))

    def test_face_targets_have_no_hair_above_the_face_outline(self):
        visual = archer.Visuals.__new__(archer.Visuals)
        for masked in (False, True):
            with self.subTest(masked=masked):
                image = Image.new('RGB', (400, 400), '#071c22')
                area = (100, 55, 300, 74)
                before = image.crop(area).tobytes()
                visual._face(image, 200, 200, 1, masked=masked)
                self.assertEqual(before, image.crop(area).tobytes())


if __name__ == '__main__':
    unittest.main()
