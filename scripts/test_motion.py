"""Offline algorithm/provenance regressions, never scientific/export approval.

Synthetic artwork and Pillow's bundled test font keep these tests network-free.
The separate real licensed-asset preview exercises the production toolchain.
"""
import copy
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw, ImageFont

import motion_spec as spec
import production_motion as motion
import production_nature as nature
import preview_motion as preview


def digest(image):
    return hashlib.sha256(image.tobytes()).hexdigest()


class FixtureTypography(nature.Typography):
    """Bundled synthetic test face; production fonts are never substituted."""
    def __init__(self, unused=None):
        self.receipts = []
        self.strings = []

    def font(self, size, face='sans', weight=600):
        return ImageFont.load_default(size=int(size))

    def text(self, image, text, *args, **kwargs):
        self.strings.append(text)
        return super().text(image, text, *args, **kwargs)


class EvidenceFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        evidence_dir = self.root / 'evidence'
        evidence_dir.mkdir()
        quote = 'Five of five monitored frogs remained healthy for seven weeks.'
        evidence = ('DOI: 10.0000/test-fixture\n' + quote + '\n').encode()
        self.evidence_path = evidence_dir / 'fixture.md'
        self.evidence_path.write_bytes(evidence)
        self.ep = {
            'id': 'UNIT-ONLY', 'slug': 'unit-fixture-not-an-episode',
            'doi': '10.0000/test-fixture', 'evidence_file': 'evidence/fixture.md',
            'evidence': {'claims': [{'claim': quote, 'location': 'Fixture Results, paragraph 1'}]},
            'production': {
                'renderer': motion.DECLARED_RENDERER,
                'motion': {'schema_version': 1, 'evidence_sha256': hashlib.sha256(evidence).hexdigest()},
                'assets': [],
                'segments': [{'speech': quote, 'captions': [quote], 'shots': [{
                    'kind': 'evidence_count', 'start': 0, 'end': 1,
                    'title': 'Survival after the freeze',
                    'motion': {'metric': {'label': 'Monitored frogs recovered', 'value': 5, 'total': 5,
                                         'unit': 'frogs', 'claim_index': 0, 'source_quote': quote,
                                         'scope': 'One controlled study; seven-week follow-up'}}
                }]}]
            }
        }
        self.root_patch = patch.object(spec, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.network_patch = patch.object(nature, 'download', side_effect=AssertionError('Unit tests must not download'))
        self.network_patch.start()
        self.addCleanup(self.network_patch.stop)

    @property
    def shot(self):
        return self.ep['production']['segments'][0]['shots'][0]

    @property
    def metric(self):
        return self.shot['motion']['metric']


class MotionEvidenceTests(EvidenceFixture):
    def test_every_licensed_asset_requires_an_exact_sha(self):
        for value in ('', 'short', 'G' * 64, '0' * 63, 'A' * 64):
            self.ep['production']['assets'] = [{'id': 'test-asset', 'sha256': value}]
            with self.subTest(sha=value), self.assertRaisesRegex(ValueError, 'pinned SHA'):
                spec.validate_motion_spec(self.ep)
        self.ep['production']['assets'] = [{'id': 'test-asset'}]
        with self.assertRaisesRegex(ValueError, 'pinned SHA'):
            spec.validate_motion_spec(self.ep)
        self.ep['production']['assets'][0]['sha256'] = 'a' * 64
        self.assertEqual(spec.validate_motion_spec(self.ep)['engine'], motion.DECLARED_RENDERER)

    def test_source_specific_scenes_cannot_be_reused_for_another_doi(self):
        for kind in ('winter', 'cells', 'glucose', 'experiment', 'scope',
                     'spider_bell', 'spider_oxygen', 'spider_probe', 'spider_gas', 'spider_scope',
                     'bee_rolling', 'bee_path', 'bee_choice', 'bee_age', 'bee_scope', 'bee_video'):
            episode = copy.deepcopy(self.ep)
            shot = episode['production']['segments'][0]['shots'][0]
            shot['kind'], shot['motion'] = kind, {}
            with self.subTest(scene=kind), self.assertRaisesRegex(ValueError, 'Source-specific'):
                spec.validate_motion_spec(episode)

    def test_valid_count_receipt_binds_entire_plan_and_evidence(self):
        receipt = spec.validate_motion_spec(self.ep)
        self.assertEqual(receipt['metrics'][0]['value'], 5)
        self.assertEqual(receipt['metrics'][0]['location'], 'Fixture Results, paragraph 1')
        self.assertFalse(receipt['measured_time_series'])
        original = receipt['spec_sha256']
        self.shot['title'] = 'Different exact export'
        self.assertNotEqual(spec.validate_motion_spec(self.ep)['spec_sha256'], original)

    def test_missing_stale_or_outside_evidence_fails(self):
        for field, value in [('evidence_file', 'evidence/missing.md'),
                             ('evidence_file', '../fixture.md'),
                             ('doi', '10.0000/wrong-paper')]:
            episode = copy.deepcopy(self.ep)
            episode[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                spec.validate_motion_spec(episode)
        self.evidence_path.write_text('changed evidence bytes', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'stale'):
            spec.validate_motion_spec(self.ep)

    def test_missing_version_and_unrecognized_options_fail(self):
        for motion_plan in (None, {}, {'schema_version': 2, 'evidence_sha256': 'x'},
                            {**self.ep['production']['motion'], 'paid_api': True}):
            episode = copy.deepcopy(self.ep)
            episode['production']['motion'] = motion_plan
            with self.subTest(plan=motion_plan), self.assertRaises(ValueError):
                spec.validate_motion_spec(episode)
        self.shot['motion']['easing'] = 'unknown'
        with self.assertRaises(ValueError):
            spec.validate_motion_spec(self.ep)

    def test_count_rejects_unverified_quote_or_changed_result(self):
        for field, value in [('source_quote', 'Four of five monitored frogs remained healthy.'),
                             ('value', 4), ('total', 6), ('claim_index', 1),
                             ('claim_index', True), ('scope', ''), ('unit', ''), ('label', '')]:
            episode = copy.deepcopy(self.ep)
            episode['production']['segments'][0]['shots'][0]['motion']['metric'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                spec.validate_motion_spec(episode)
        self.ep['evidence']['claims'][0]['location'] = ''
        with self.assertRaises(ValueError):
            spec.validate_motion_spec(self.ep)

    def test_invalid_count_types_ranges_and_nonfinite_values_fail(self):
        for field in ('value', 'total'):
            for value in (-1, True, 2.5, float('inf'), float('nan'), 31, '5', None):
                episode = copy.deepcopy(self.ep)
                episode['production']['segments'][0]['shots'][0]['motion']['metric'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    spec.validate_motion_spec(episode)
        self.metric['total'] = 0
        with self.assertRaises(ValueError):
            spec.validate_motion_spec(self.ep)

    def test_metric_must_have_dedicated_count_scene_and_source(self):
        self.shot['kind'] = 'cells'
        with self.assertRaises(ValueError):
            spec.validate_motion_spec(self.ep)
        self.shot['kind'] = 'evidence_count'
        for key in list(self.metric):
            episode = copy.deepcopy(self.ep)
            del episode['production']['segments'][0]['shots'][0]['motion']['metric'][key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                spec.validate_motion_spec(episode)

    def test_fractional_timings_reject_gaps_overlaps_nonfinite_and_empty_coverage(self):
        for start, end in ((.1, 1), (0, .9), (0, 0), (0, 1.1),
                           (float('nan'), 1), (0, float('inf')), (False, 1), (0, '1')):
            episode = copy.deepcopy(self.ep)
            episode['production']['segments'][0]['shots'][0].update(start=start, end=end)
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                spec.validate_motion_spec(episode)
        first = copy.deepcopy(self.shot)
        second = copy.deepcopy(self.shot)
        first['end'], second['start'] = .6, .5
        self.ep['production']['segments'][0]['shots'] = [first, second]
        with self.assertRaises(ValueError):
            spec.validate_motion_spec(self.ep)


class MotionFrameTests(EvidenceFixture):
    def setUp(self):
        super().setUp()
        self.font_patch = patch.object(motion, 'Typography', FixtureTypography)
        self.font_patch.start()
        self.addCleanup(self.font_patch.stop)
        self.vis = motion.Visuals(self.ep, self.root / 'render', artifact_root=self.root / 'preview')
        # The temporary test artwork contains asymmetric spatial detail so a
        # camera transform must change pixels; a flat fill would not exercise it.
        picture = Image.new('RGB', (1200, 2200), '#153d45')
        d = ImageDraw.Draw(picture)
        for x in range(0, 1200, 75):
            d.rectangle((x, 0, x + 24, 2199), fill=(x % 255, 100, 180))
        d.ellipse((500, 600, 1100, 1800), fill='#b4ce96')
        self.vis.photos['synthetic'] = picture
        self.vis.info['synthetic'] = {'focus': [.5, .5]}

    def test_random_access_frames_do_not_depend_on_render_order(self):
        shot = {**self.shot, 'start': 0., 'end': 5.}
        first = digest(self.vis.frame(shot, .2, 'An exact test caption.'))
        self.vis.frame(shot, 4.4, 'An exact test caption.')
        self.vis.frame(shot, .05, 'An exact test caption.')
        self.assertEqual(first, digest(self.vis.frame(shot, .2, 'An exact test caption.')))

    def test_titles_camera_and_ecological_art_have_real_motion(self):
        shot = {**self.shot, 'start': 0., 'end': 5.}
        early = self.vis.frame(shot, 0).crop((66, 285, 1014, 605))
        later = self.vis.frame(shot, 1).crop((66, 285, 1014, 605))
        self.assertNotEqual(digest(early), digest(later))
        self.assertNotEqual(digest(self.vis.photograph('synthetic', 0)),
                            digest(self.vis.photograph('synthetic', 6)))
        self.assertEqual(digest(self.vis.photograph('synthetic', 2)),
                         digest(self.vis.photograph('synthetic', 2)))
        for kind in ('cells', 'spider_oxygen', 'bee_rolling'):
            with self.subTest(scene=kind):
                self.assertNotEqual(digest(self.vis.diagram(kind, 0, .2, {})),
                                    digest(self.vis.diagram(kind, 1.3, .2, {})))

    def test_caption_and_logo_are_single_stable_layers_during_transition(self):
        first = {'kind': 'scope', 'title': 'The study limits', 'start': 0., 'end': 3.}
        second = {**self.shot, 'start': 3., 'end': 7.}
        self.vis.timeline = [first, second]
        frames = [self.vis.frame(second, t, 'Five of five recovered.') for t in (3, 3.18, 3.5)]
        self.assertEqual(len({digest(image.crop((50, 650, 1030, 1425))) for image in frames}), 3)
        for region in ((66, 1477, 1014, 1610), (82, 72, 222, 212)):
            for image in frames[1:]:
                self.assertIsNone(ImageChops.difference(frames[0].crop(region), image.crop(region)).getbbox())

    def test_count_reveal_never_prints_an_intermediate_result(self):
        for local in (0, .1, .4, .8, 2):
            self.vis.type.strings.clear()
            self.vis.evidence_count(self.shot, local)
            numeric_results = [s for s in self.vis.type.strings if re.fullmatch(r'\d+ of \d+', s)]
            self.assertEqual(numeric_results, ['5 of 5'])
            self.assertIn('Animated reveal · not a time series', self.vis.type.strings)

    def test_count_transitions_fade_all_digits_together_without_spatial_mask(self):
        # Three separated glyph sentinels stand for numerator/connector/
        # denominator. A horizontal wipe would change them at different times.
        neutral = Image.new('RGB', (nature.W, nature.H), (0, 0, 0))
        old, new = neutral.copy(), neutral.copy()
        old_points = [(120, 800), (500, 800), (900, 800)]
        new_points = [(120, 1000), (500, 1000), (900, 1000)]
        for image, points in ((old, old_points), (new, new_points)):
            draw = ImageDraw.Draw(image)
            for x, y in points:
                draw.rectangle((x-10, y-10, x+10, y+10), fill='white')
        self.vis.background = neutral
        blend = Image.blend
        for previous_kind, current_kind in (('scope', 'evidence_count'),
                                             ('evidence_count', 'scope'),
                                             ('evidence_count', 'evidence_count')):
            previous = {'kind': previous_kind, 'start': 0., 'end': 3.}
            current = {'kind': current_kind, 'start': 3., 'end': 7.}
            self.vis.timeline = [previous, current]
            with self.subTest(previous=previous_kind, current=current_kind), \
                    patch.object(self.vis, 'artwork', return_value=old), \
                    patch.object(Image, 'composite', side_effect=AssertionError('No numerical wipes')), \
                    patch.object(Image, 'blend', wraps=blend) as called:
                for elapsed in (.03, .09, .15, .18, .21, .27, .33):
                    frame = self.vis.transition(new, current, 3. + elapsed)
                    self.assertEqual(len({frame.getpixel(point) for point in old_points}), 1)
                    self.assertEqual(len({frame.getpixel(point) for point in new_points}), 1)
                    if elapsed < .18:
                        self.assertTrue(all(frame.getpixel(point) == (0, 0, 0) for point in new_points))
                        self.assertIs(called.call_args.args[0], old)
                        self.assertIs(called.call_args.args[1], neutral)
                    else:
                        self.assertTrue(all(frame.getpixel(point) == (0, 0, 0) for point in old_points))
                        self.assertIs(called.call_args.args[0], neutral)
                        self.assertIs(called.call_args.args[1], new)
                middle = self.vis.transition(new, current, 3.18)
                self.assertIsNone(ImageChops.difference(middle, neutral).getbbox())

    def test_noncount_artwork_keeps_the_feathered_wipe(self):
        previous = {'kind': 'scope', 'start': 0., 'end': 3.}
        current = {'kind': 'cells', 'start': 3., 'end': 7.}
        self.vis.timeline = [previous, current]
        old = Image.new('RGB', (nature.W, nature.H), 'black')
        new = Image.new('RGB', (nature.W, nature.H), 'white')
        with patch.object(self.vis, 'artwork', return_value=old), \
                patch.object(Image, 'blend', side_effect=AssertionError('Preserve the non-count wipe')):
            midpoint = self.vis.transition(new, current, 3.18)
        self.assertEqual(midpoint.getpixel((100, 800)), (255, 255, 255))
        self.assertEqual(midpoint.getpixel((900, 800)), (0, 0, 0))

    def test_direct_render_defenses_reject_invalid_metric_or_time(self):
        for value in (-1, True, 2.5, float('inf'), float('nan'), 6):
            shot = copy.deepcopy(self.shot)
            shot['motion']['metric']['value'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.vis.evidence_count(shot, .5)
        for value in (float('nan'), float('inf'), -float('inf'), True, '1'):
            with self.subTest(time=value), self.assertRaises(ValueError):
                self.vis.frame(self.shot, value)

    def test_visual_initialization_does_not_rebind_frozen_globals(self):
        originals = {name: getattr(nature, name) for name in ('Visuals', 'Typography', 'VERSION', 'MEDIA', 'QA', 'render')}
        render_globals = dict(nature.render.__globals__)
        other = motion.Visuals(self.ep, self.root / 'second-render', artifact_root=self.root / 'preview')
        other.frame(self.shot, .5)
        for name, original in originals.items():
            self.assertIs(getattr(nature, name), original)
        self.assertEqual(set(render_globals), set(nature.render.__globals__))
        for key, value in render_globals.items():
            self.assertIs(nature.render.__globals__[key], value)

    def test_pipeline_clone_redirects_outputs_and_keeps_approval_unclaimed(self):
        # Exercise the actual isolated wrapper with a minimal pipeline body,
        # avoiding expensive audio/encoding; it is explicitly not render QA.
        def pipeline(episode, voice, output):
            visuals = Visuals(episode, output)  # injected private global
            timeline, _, _, _ = voice.make(episode, output)
            return {'test_frame': digest(visuals.frame(timeline[0], .2)),
                    'test_media': str(MEDIA), 'test_qa': str(QA)}
        voice = SimpleNamespace(asr=object(), make=lambda ep, out: ([{**self.shot, 'end': 4.}], [], [], 4.))
        old_visuals, old_typography = nature.Visuals, nature.Typography
        media, qa = self.root / 'preview/media', self.root / 'preview/qa'
        with patch.object(nature, 'render', pipeline):
            result = motion.render(self.ep, voice, self.root / 'render', media_dir=media, qa_dir=qa)
        self.assertEqual(result['test_media'], str(media))
        self.assertEqual(result['test_qa'], str(qa))
        self.assertTrue(result['motion_review_required'])
        self.assertFalse(result['motion_review_claimed'])
        self.assertFalse(result['branding_review_claimed'])
        self.assertIs(nature.Visuals, old_visuals)
        self.assertIs(nature.Typography, old_typography)
        with self.assertRaises(ValueError):
            motion.render(self.ep, voice, self.root / 'render', media_dir=media)


class AlignedTimingTests(unittest.TestCase):
    def test_good_timeline_and_invalid_voice_outputs(self):
        good = [{'start': 0., 'end': 2.}, {'start': 2., 'end': 5.}]
        motion.validate_aligned_timeline(good, 5.)
        cases = [([], 5), (good, 4), (good, 6), (good, float('nan')), (good, True),
                 ([{'start': 0, 'end': 0}], 1), ([{'start': .1, 'end': 5}], 5),
                 ([{'start': 0, 'end': 2}, {'start': 1.9, 'end': 5}], 5),
                 ([{'start': 0, 'end': 2}, {'start': 2.1, 'end': 5}], 5)]
        for field in ('start', 'end'):
            for value in (float('nan'), float('inf'), True, '2', None):
                bad = copy.deepcopy(good)
                bad[1][field] = value
                cases.append((bad, 5))
        for timeline, duration in cases:
            with self.subTest(timeline=timeline, duration=duration), self.assertRaises(ValueError):
                motion.validate_aligned_timeline(timeline, duration)


class PreviewIsolationTests(EvidenceFixture):
    def setUp(self):
        super().setUp()
        self.ep.update(publication_enabled=False, posts=[])
        episodes = self.root / 'episodes'
        episodes.mkdir()
        original = copy.deepcopy(self.ep)
        original['publication_enabled'] = True
        (episodes / 'unit-only.json').write_text(json.dumps(original), encoding='utf-8')
        (self.root / 'quality').mkdir()
        (self.root / 'quality/releases.json').write_text(json.dumps({
            'UNIT-ONLY': {'decision': 'release', 'fingerprint': 'test-approved-fingerprint'}}), encoding='utf-8')
        self.path = self.root / 'preview.json'
        self.save(self.ep)
        # Only the historical approval calculation is mocked. All preview
        # destination, story identity, post and motion guards execute normally.
        for patcher in (
                patch.object(preview, 'ROOT', self.root),
                patch.object(preview.build, 'render_fingerprint', return_value='test-approved-fingerprint'),
                patch.object(preview.build, 'select_renderer', return_value=object()),
                patch.object(preview, 'validate_pre_render', return_value='test-source-hash'),
                patch.object(preview.build, 'validate')):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.private_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.private_temp.cleanup)
        self.output = Path(self.private_temp.name) / 'new-preview'

    def save(self, episode):
        self.path.write_text(json.dumps(episode), encoding='utf-8')

    def test_private_prepare_has_no_write_or_publication_effects(self):
        before = {p.relative_to(self.root): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob('*') if p.is_file()}
        episode, output, source, approved = preview.prepare(self.path, self.output)
        self.assertEqual(output, self.output.resolve())
        self.assertFalse(episode['publication_enabled'])
        self.assertEqual(episode['posts'], [])
        self.assertEqual(source, 'test-source-hash')
        self.assertEqual(approved, 'test-approved-fingerprint')
        self.assertFalse(output.exists())
        self.assertEqual(before, {p.relative_to(self.root): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in self.root.rglob('*') if p.is_file()})

    def test_repository_and_nonempty_destinations_are_rejected(self):
        for output in (self.root, self.root / 'site/media', self.root / 'render-cache'):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'outside'):
                preview.prepare(self.path, output)
        self.output.mkdir()
        (self.output / 'existing.txt').write_text('Keep this export')
        with self.assertRaisesRegex(ValueError, 'empty output'):
            preview.prepare(self.path, self.output)
        self.assertEqual((self.output / 'existing.txt').read_text(), 'Keep this export')

    def test_publication_posts_source_and_narration_mutations_fail(self):
        for key, value in (('publication_enabled', True), ('posts', [{'id': 'new-post'}]),
                           ('doi', '10.0000/new'), ('evidence_file', 'evidence/other.md'),
                           ('evidence', {}), ('editorial_story', {'new': 'claim'}), ('slides', [])):
            changed = copy.deepcopy(self.ep)
            changed[key] = value
            self.save(changed)
            with self.subTest(field=key), self.assertRaises(ValueError):
                preview.prepare(self.path, self.output)
        for key, value in (('speech', 'A changed claim'), ('captions', ['Changed caption'])):
            changed = copy.deepcopy(self.ep)
            changed['production']['segments'][0][key] = value
            self.save(changed)
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, 'narration or captions'):
                preview.prepare(self.path, self.output)

    def test_unapproved_source_fingerprint_and_episode_escape_fail(self):
        with patch.object(preview.build, 'render_fingerprint', return_value='different-source'):
            with self.assertRaisesRegex(ValueError, 'approved source'):
                preview.prepare(self.path, self.output)
        self.ep['id'] = '../../../elsewhere'
        self.save(self.ep)
        with self.assertRaisesRegex(ValueError, 'episode identity'):
            preview.prepare(self.path, self.output)

    def test_modified_or_escaping_slug_fails_before_render(self):
        for slug in ('different-valid-slug', '../another-output', str(self.output / 'outside')):
            changed = copy.deepcopy(self.ep)
            changed['slug'] = slug
            self.save(changed)
            with self.subTest(slug=slug), self.assertRaisesRegex(ValueError, 'approved story slug'):
                preview.prepare(self.path, self.output)
        self.assertFalse(self.output.exists())


class StudyFootageCacheTests(unittest.TestCase):
    def test_complete_hash_checked_decode_only_is_reused(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / 'source.webm'
            source.write_bytes(b'explicit synthetic cache-test source; not video')
            def decode(command):
                pattern = str(command[-1])
                for index in range(1, 4):
                    Image.new('RGB', (32, 18), (index * 40, 70, 90)).save(pattern % index)
            with patch.object(nature, 'sh', side_effect=decode) as decoder:
                frames = motion.decode_study_frames(source, root / 'render')
                marker = frames[0].parent / 'complete.json'
                self.assertEqual(len(json.loads(marker.read_text())['frames']), 3)
                self.assertEqual(motion.decode_study_frames(source, root / 'render'), frames)
                self.assertEqual(decoder.call_count, 1)
                frames[0].write_bytes(b'corrupt')
                motion.decode_study_frames(source, root / 'render')
                self.assertEqual(decoder.call_count, 2)
                marker.unlink()
                motion.decode_study_frames(source, root / 'render')
                self.assertEqual(decoder.call_count, 3)
                frames[-1].unlink()
                motion.decode_study_frames(source, root / 'render')
                self.assertEqual(decoder.call_count, 4)

    def test_failed_or_empty_decode_has_no_completion_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / 'source.webm'
            source.write_bytes(b'synthetic unit source')
            def fail(command):
                Image.new('RGB', (32, 18), 'red').save(str(command[-1]) % 1)
                raise RuntimeError('simulated decoder failure')
            with patch.object(nature, 'sh', side_effect=fail), self.assertRaises(RuntimeError):
                motion.decode_study_frames(source, root / 'render')
            self.assertFalse(list((root / 'render').rglob('complete.json')))
            with patch.object(nature, 'sh'), self.assertRaisesRegex(ValueError, 'No actual frames'):
                motion.decode_study_frames(source, root / 'render')
            self.assertFalse(list((root / 'render').rglob('complete.json')))


if __name__ == '__main__':
    unittest.main()
