"""Regression coverage for release preservation and the prospective motion gate."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import build
import build_motion
from editorial_gate import validate_pre_render
from test_branding_gate import branded_release


# Linux checkout fingerprints from main 1333e10b470b5500cc5a00b839f2af7ca975e8e2.
# Include held/rejected history: integration must not silently rewrite it either.
BASELINE = {
    'TT-002': '3107c7add56b0123b6365d75b1c015e8f1d564e748b77f500773226d64344a54',
    'TT-003': 'de6e3de79586e0b1839f97649c2441c76db19ca84c00f7d868d33e761e89bbc8',
    'TT-004': 'a70c13bde0d36f7cb62fc7d9ecef687af36728f180391931265041a5ce166223',
    'TT-005': '3048cc50e4baf83085f78b564094ebf80e930b711a55e1733e5f0fe8d05d3c8b',
    'TT-006': 'd34a246d6540a3aea25644c46a449ddbdc2816486b1cf6f67034f3f3b11ee4c6',
    'TT-007': '828b394d335136f3f97f68f62e0ddf55ebad6ce3d161c7c67fbb96698cb873db',
}
RECEIPT = {'schema_version': 1, 'engine': 'nature-motion-10',
           'spec_sha256': 'motion-spec', 'evidence_sha256': 'evidence', 'metrics': []}


def motion_release():
    episode, manifest, release = branded_release()
    episode['production']['renderer'] = build_motion.motion_renderer.DECLARED_RENDERER
    manifest.update(renderer=build_motion.motion_renderer.VERSION,
                    declared_renderer=build_motion.motion_renderer.DECLARED_RENDERER,
                    motion_standard=build_motion.MOTION_STANDARD,
                    motion_review_required=True, motion=copy.deepcopy(RECEIPT),
                    motion_spec_sha256=RECEIPT['spec_sha256'],
                    motion_provenance={'engine': 'pillow-ffmpeg', 'deterministic': True,
                                       'paid_services': False,
                                       'spec_sha256': RECEIPT['spec_sha256']})
    release['motion_review'] = {
        **{k: copy.deepcopy(manifest[k]) for k in
           ('fingerprint', 'files', 'evidence_sha256', 'motion_spec_sha256')},
        'standard': build_motion.MOTION_STANDARD, 'decision': 'pass',
        'reviewer': 'independent motion export reviewer',
        'reviewed_at': '2026-11-09T10:00:00Z', 'source_sha256': 'source',
        'independent_from_script_author': True,
        **{k: True for k in build_motion.MOTION_FRAME_CHECKS},
        'checks': {key: {'decision': 'pass', 'finding': 'Observed rendered ' + key,
                         'basis': 'Specific encoded shot and evidence source inspected'}
                   for key in build_motion.MOTION_CHECKS},
    }
    return episode, manifest, release


class MotionIntegration(unittest.TestCase):
    def test_new_episodes_cannot_fall_back_to_legacy_renderers(self):
        episode, _, _ = branded_release()
        for episode_id in ('TT-001', 'TT-008', 'TT-999', None):
            episode['id'] = episode_id
            for renderer in ('nature-branded-9', 'nature-story-8', 'ecology-story-7',
                             None, 'invented-renderer'):
                episode['production']['renderer'] = renderer
                for posts in ([{'format': 'REEL'}], [{'format': 'SHORT'}],
                              [{'format': 'CAROUSEL'}], []):
                    episode['posts'] = posts
                    with self.subTest(id=episode_id, renderer=renderer, posts=posts):
                        with self.assertRaisesRegex(ValueError, 'New production episodes require nature-motion-10'):
                            build_motion.select_renderer(episode)

    def test_new_legacy_release_is_rejected_even_when_old_gates_pass(self):
        episode, manifest, release = branded_release()
        episode['id'] = 'TT-008'
        self.assertTrue(build.release_ok(release, manifest, episode))
        for posts in ([{'format': 'REEL'}], [{'format': 'SHORT'}],
                      [{'format': 'CAROUSEL'}], []):
            episode['posts'] = posts
            with self.subTest(posts=posts):
                self.assertFalse(build_motion.release_ok(release, manifest, episode))
        self.assertFalse(build_motion.release_ok(release, manifest, None))
        self.assertFalse(build_motion.release_ok(release, manifest, {}))

    def test_new_episode_with_motion_and_all_reviews_remains_eligible(self):
        episode, manifest, release = motion_release()
        episode['id'] = 'TT-008'
        with patch.object(build_motion, 'validate_motion_spec', return_value=RECEIPT):
            self.assertIs(build_motion.select_renderer(episode), build_motion.motion_renderer)
            self.assertTrue(build_motion.release_ok(release, manifest, episode))
            release.pop('motion_review')
            self.assertFalse(build_motion.release_ok(release, manifest, episode))

    def test_failed_preservation_preflight_cannot_start_build(self):
        with patch.object(build_motion, 'preserve_legacy_releases', side_effect=ValueError('unverified archive')):
            with patch.object(build_motion.types, 'FunctionType') as pipeline:
                with self.assertRaisesRegex(ValueError, 'unverified archive'):
                    build_motion.main()
                pipeline.assert_not_called()

    def test_all_historical_fingerprints_and_decisions_are_preserved(self):
        original = Path.read_bytes
        # Mirror Linux LF checkout without rewriting or normalizing production IO.
        with patch.object(Path, 'read_bytes', lambda path: original(path).replace(b'\r\n', b'\n')):
            releases = build.read(build.ROOT / 'quality/releases.json')
            for episode_id, expected in BASELINE.items():
                with self.subTest(episode=episode_id):
                    path = build.ROOT / ('episodes/' + episode_id.lower() + '.json')
                    episode = build.read(path)
                    evidence = build.ROOT / episode['evidence_file']
                    source = validate_pre_render(episode, evidence.read_text(encoding='utf-8'))
                    renderer = build_motion.select_renderer(episode)
                    self.assertIs(renderer, build.select_renderer(episode))
                    actual = build_motion.render_fingerprint(path, evidence, renderer, source)
                    self.assertEqual(actual, expected)
                    self.assertEqual(releases[episode_id]['fingerprint'], expected)
                    manifest = copy.deepcopy(releases[episode_id])
                    manifest.update(editorial_style=episode['production'].get('editorial_style'),
                                    editorial_standard=episode['production'].get('editorial_standard'),
                                    editorial_source_sha256=source,
                                    script_author=episode.get('script_author', 'Toxic Tales production editor'),
                                    declared_renderer=episode['production'].get('renderer'),
                                    renderer=renderer.VERSION)
                    if renderer is build.branded_renderer:
                        _, asset = renderer.load_brand_logo()
                        manifest.update(branding_standard=renderer.BRANDING_STANDARD,
                                        branding_review_required=True, brand_asset=asset,
                                        branding_layout={'logo_visible_from_opening': True,
                                            'logo_box_xywh': list(renderer.LOGO_BOX),
                                            'production_footer': False, 'progress_bar': False,
                                            'field_notes_or_episode_code': False,
                                            'scientific_labels_and_speech_captions': True})
                    self.assertEqual(build_motion.release_ok(releases[episode_id], manifest, episode),
                                     build.release_ok(releases[episode_id], manifest, episode))
                    self.assertEqual(build_motion.release_ok(releases[episode_id], manifest, episode),
                                     episode_id in {'TT-004', 'TT-005', 'TT-006', 'TT-007'})

    def test_motion_selection_is_explicit_and_validated(self):
        episode, _, _ = motion_release()
        with patch.object(build_motion, 'validate_motion_spec', return_value=RECEIPT) as validator:
            self.assertIs(build_motion.select_renderer(episode), build_motion.motion_renderer)
            validator.assert_called_once_with(episode)
        with patch.object(build_motion, 'validate_motion_spec', side_effect=ValueError('stale evidence')):
            with self.assertRaisesRegex(ValueError, 'stale evidence'):
                build_motion.select_renderer(episode)
        episode['production']['renderer'] = 'invented-renderer'
        with self.assertRaises(AssertionError):
            build_motion.select_renderer(episode)

    def test_complete_motion_review_preserves_all_existing_gates(self):
        episode, manifest, release = motion_release()
        with patch.object(build_motion, 'validate_motion_spec', return_value=RECEIPT):
            self.assertTrue(build_motion.release_ok(release, manifest, episode))
            for field in ('motion_review', 'branding_review', 'final_editorial_review',
                          'scientific_review', 'audio_review', 'visual_review', 'narrative_review'):
                changed = copy.deepcopy(release)
                changed.pop(field)
                with self.subTest(missing=field):
                    self.assertFalse(build_motion.release_ok(changed, manifest, episode))
            # No historical episode-ID exception for a new motion render.
            episode['id'] = 'TT-005'
            changed = copy.deepcopy(release)
            changed.pop('branding_review')
            self.assertFalse(build_motion.release_ok(changed, manifest, episode))
            historical = build.read(build.ROOT / 'quality/releases.json')
            for episode_id in BASELINE:
                episode['id'] = episode_id
                with self.subTest(old_release=episode_id):
                    self.assertFalse(build_motion.release_ok(historical[episode_id], manifest, episode))

    def test_motion_review_rejects_stale_source_bytes_and_incomplete_inspection(self):
        episode, manifest, release = motion_release()
        changes = {k: 'changed' for k in ('fingerprint', 'files', 'evidence_sha256',
                                         'source_sha256', 'motion_spec_sha256')}
        changes.update({k: False for k in build_motion.MOTION_FRAME_CHECKS})
        changes.update(independent_from_script_author=False, reviewer='script author',
                       decision='hold', standard='invented', reviewed_at='')
        with patch.object(build_motion, 'validate_motion_spec', return_value=RECEIPT):
            for key, value in changes.items():
                changed = copy.deepcopy(release)
                changed['motion_review'][key] = value
                with self.subTest(field=key):
                    self.assertFalse(build_motion.release_ok(changed, manifest, episode))
            for key in build_motion.MOTION_CHECKS:
                changed = copy.deepcopy(release)
                changed['motion_review']['checks'][key]['finding'] = 'pass'
                with self.subTest(check=key):
                    self.assertFalse(build_motion.release_ok(changed, manifest, episode))

    def test_provenance_cannot_bypass_motion_release(self):
        episode, manifest, release = motion_release()
        with patch.object(build_motion, 'validate_motion_spec', return_value=RECEIPT):
            for key in ('motion', 'motion_review_required', 'motion_standard',
                        'motion_spec_sha256', 'motion_provenance', 'declared_renderer'):
                changed = copy.deepcopy(manifest)
                changed.pop(key)
                with self.subTest(field=key):
                    self.assertFalse(build_motion.release_ok(release, changed, episode))
            for key, value in (('engine', 'paid-api'), ('deterministic', False),
                               ('paid_services', True), ('spec_sha256', 'stale')):
                changed = copy.deepcopy(manifest)
                changed['motion_provenance'][key] = value
                with self.subTest(provenance=key):
                    self.assertFalse(build_motion.release_ok(release, changed, episode))
            self.assertFalse(build_motion.release_ok(release, manifest, None))
        with patch.object(build_motion, 'validate_motion_spec', side_effect=ValueError('stale')):
            self.assertFalse(build_motion.release_ok(release, manifest, episode))

    def test_fingerprint_tracks_new_dependencies_and_keeps_legacy_functions_isolated(self):
        path = build.ROOT / 'episodes/tt-005.json'
        evidence = build.ROOT / build.read(path)['evidence_file']
        original = Path.read_bytes
        baseline = build_motion.render_fingerprint(path, evidence, build_motion.motion_renderer, 'source')
        for relative in build_motion.MOTION_DEPENDENCIES:
            target = build.ROOT / relative
            def changed(current, target=target):
                return original(current) + (b'changed' if current == target else b'')
            with self.subTest(dependency=relative), patch.object(Path, 'read_bytes', changed):
                self.assertNotEqual(baseline, build_motion.render_fingerprint(
                    path, evidence, build_motion.motion_renderer, 'source'))
        self.assertEqual(build.select_renderer.__module__, 'build')
        self.assertEqual(build.render_fingerprint.__module__, 'build')
        self.assertEqual(build.release_ok.__module__, 'build')
        with self.assertRaises(ValueError):
            build_motion.render_fingerprint(path, evidence, build_motion.motion_renderer, None)


if __name__ == '__main__':
    unittest.main()
