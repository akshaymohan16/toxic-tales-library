"""Prospective brand checks cannot weaken or invalidate frozen approvals."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import build
from editorial_gate import STANDARD, validate_pre_render
from test_editorial_gate import review_record


def branded_release():
    _, asset = build.branded_renderer.load_brand_logo()
    manifest = {
        'renderer': build.branded_renderer.VERSION,
        'declared_renderer': build.branded_renderer.DECLARED_RENDERER,
        'branding_standard': build.branded_renderer.BRANDING_STANDARD,
        'branding_review_required': True,
        'brand_asset': asset,
        'branding_layout': {
            'logo_visible_from_opening': True,
            'logo_box_xywh': list(build.branded_renderer.LOGO_BOX),
            'production_footer': False, 'progress_bar': False,
            'field_notes_or_episode_code': False,
            'scientific_labels_and_speech_captions': True,
        },
        'editorial_style': 'science-journalism', 'editorial_standard': STANDARD,
        'editorial_source_sha256': 'source', 'fingerprint': 'future-render',
        'files': {'media/movie.mp4': 'video-sha', 'media/cover.jpg': 'cover-sha'},
        'evidence_sha256': 'evidence', 'script_author': 'script author',
    }
    identity = {k: copy.deepcopy(manifest[k]) for k in ('fingerprint', 'files', 'evidence_sha256')}
    editorial = review_record()
    editorial.update(**identity, source_sha256='source',
                     independent_from_script_author=True, reviewed_encoded_frames=True)
    branding = {
        **identity,
        'standard': build.branded_renderer.BRANDING_STANDARD,
        'decision': 'pass', 'reviewer': 'independent export editor',
        'reviewed_at': '2026-11-07T22:00:00Z',
        'independent_from_script_author': True,
        'logo_sha256': asset['sha256'],
        **{key: True for key in build.BRANDING_FRAME_CHECKS},
        'checks': {
            key: {'decision': 'pass', 'finding': 'Specific observed result for ' + key,
                  'basis': 'Encoded opening, shot boundaries, final frame, cover and caption/research record'}
            for key in build.BRANDING_CHECKS
        },
    }
    release = {**identity, 'decision': 'release',
               'reviewed_contact_sheet': 'Exact encoded contact sheet inspected',
               'scientific_review': 'Claims and limitations traced to the full paper',
               'visual_review': 'Actual figures and final frames inspected',
               'audio_review': 'Final narration and critical terms checked',
               'narrative_review': 'Opening context, mechanism and bounded payoff inspected',
               'final_editorial_review': editorial, 'branding_review': branding}
    episode = {'id': 'TT-006', 'production': {'renderer': build.branded_renderer.DECLARED_RENDERER},
               'posts': [{'format': 'REEL'}]}
    return episode, manifest, release


class BrandingGates(unittest.TestCase):
    def test_new_reel_requires_explicit_branded_renderer(self):
        episode, _, _ = branded_release()
        self.assertIs(build.select_renderer(episode), build.branded_renderer)
        for renderer in ('nature-story-8', 'ecology-story-7', None, 'invented-renderer'):
            with self.subTest(renderer=renderer):
                episode['production']['renderer'] = renderer
                with self.assertRaisesRegex(AssertionError, 'Future Reels require'):
                    build.select_renderer(episode)

    def test_complete_independent_branding_review_can_release(self):
        episode, manifest, release = branded_release()
        self.assertTrue(build.release_ok(release, manifest, episode))
        del release['branding_review']
        self.assertFalse(build.release_ok(release, manifest, episode))

    def test_brand_review_rejects_stale_files_logo_and_missing_frame_coverage(self):
        episode, manifest, release = branded_release()
        changes = {key: 'changed' for key in ('fingerprint', 'files', 'evidence_sha256', 'logo_sha256')}
        changes.update({key: False for key in build.BRANDING_FRAME_CHECKS})
        changes.update(independent_from_script_author=False, reviewer='script author')
        for key, value in changes.items():
            with self.subTest(field=key):
                changed = copy.deepcopy(release)
                changed['branding_review'][key] = value
                self.assertFalse(build.release_ok(changed, manifest, episode))

    def test_empty_or_failed_observations_do_not_count_as_visual_review(self):
        episode, manifest, release = branded_release()
        for key in build.BRANDING_CHECKS:
            for field, value in (('finding', 'checked'), ('basis', ''), ('decision', 'fail')):
                with self.subTest(check=key, field=field):
                    changed = copy.deepcopy(release)
                    changed['branding_review']['checks'][key][field] = value
                    self.assertFalse(build.release_ok(changed, manifest, episode))

    def test_wrong_logo_and_forbidden_layout_cannot_be_reviewed_into_release(self):
        episode, manifest, release = branded_release()
        for key in ('production_footer', 'progress_bar', 'field_notes_or_episode_code'):
            with self.subTest(layout=key):
                changed = copy.deepcopy(manifest)
                changed['branding_layout'][key] = True
                self.assertFalse(build.release_ok(release, changed, episode))
        changed = copy.deepcopy(manifest)
        changed['brand_asset']['sha256'] = 'unapproved-logo'
        release['branding_review']['logo_sha256'] = 'unapproved-logo'
        self.assertFalse(build.release_ok(release, changed, episode))

    def test_removing_new_manifest_flags_cannot_bypass_episode_gate(self):
        episode, manifest, release = branded_release()
        for key in ('declared_renderer', 'branding_review_required', 'branding_standard'):
            manifest.pop(key)
        self.assertFalse(build.release_ok(release, manifest, episode))

    def test_historical_exemption_is_exact_fingerprint_not_episode_id(self):
        for episode_id, fingerprint in build.FROZEN_BRANDING_EXPORTS.items():
            episode = {'id': episode_id, 'posts': [{'format': 'REEL'}]}
            self.assertTrue(build.branding_review_ok(None, {'fingerprint': fingerprint}, episode))
            self.assertFalse(build.branding_review_ok(None, {'fingerprint': 'changed-export'}, episode))
        self.assertFalse(build.branding_review_ok(None, {'fingerprint': 'legacy'},
                                                  {'id': 'TT-003', 'posts': [{'format': 'REEL'}]}))

    def test_approved_frog_fingerprint_is_unchanged(self):
        path = build.ROOT / 'episodes/tt-005.json'
        episode = build.read(path)
        evidence = build.ROOT / episode['evidence_file']
        source = validate_pre_render(episode, evidence.read_text(encoding='utf-8'))
        renderer = build.select_renderer(episode)
        self.assertIs(renderer, build.nature_renderer)
        # The Windows connector mirror can contain CRLF; the source export and
        # Linux render checkout use LF. Simulate that checkout in-memory only.
        # Production fingerprinting remains byte-exact; frozen files are never
        # rewritten by this test or silently normalised by build.py.
        original_read = Path.read_bytes
        def checkout_bytes(current):
            return original_read(current).replace(b'\r\n', b'\n')
        with patch.object(Path, 'read_bytes', checkout_bytes):
            self.assertEqual(build.render_fingerprint(path, evidence, renderer, source),
                             build.FROZEN_BRANDING_EXPORTS['TT-005'])

    def test_branded_fingerprint_tracks_inherited_renderer_logo_and_new_gate(self):
        path = build.ROOT / 'episodes/tt-005.json'
        evidence = build.ROOT / build.read(path)['evidence_file']
        baseline = build.render_fingerprint(path, evidence, build.branded_renderer, 'reviewed')
        original_read = Path.read_bytes
        for name in ('scripts/production_nature.py', 'scripts/production_pilot.py',
                     'assets/branding/toxic-tales-logo.json', 'quality/BRANDING_STANDARD.md', 'scripts/build.py'):
            target = build.ROOT / name
            def changed_read(current, target=target):
                data = original_read(current)
                return data + b'\nchanged-for-dependency-test' if current == target else data
            with self.subTest(dependency=name), patch.object(Path, 'read_bytes', changed_read):
                self.assertNotEqual(build.render_fingerprint(path, evidence, build.branded_renderer, 'reviewed'), baseline)


if __name__ == '__main__':
    unittest.main()
