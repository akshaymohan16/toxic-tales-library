import copy
import unittest

from editorial_gate import (CHECKS, STANDARD, editorial_source_sha256,
                            final_editorial_ok, validate_pre_render)


def review_record():
    return {
        'standard': STANDARD, 'reviewer': 'independent test editor',
        'reviewed_at': '2026-11-07T18:00:00Z', 'decision': 'pass',
        'checks': {key: {'decision': 'pass',
                         'finding': 'Specific observation for ' + key,
                         'basis': 'Relevant opening line, shot or evidence location'}
                   for key in CHECKS},
    }


def reviewed_episode():
    ep = {
        'id': 'TT-004', 'publication_enabled': False,
        'production': {'editorial_style': 'science-journalism',
                       'editorial_standard': STANDARD,
                       'segments': [{'speech': 'An explicit ecological question.'}],
                       'assets': [{'url': 'https://example.org/reference-a.mp4'}]},
        'editorial_story': {
            'audience': 'Curious nonspecialists', 'subject': 'A freshwater organism',
            'setting': 'A specified pond', 'opening_context': 'Concrete opening situation',
            'normal_expectation': 'The expectation needed to understand the surprise',
            'story_selection': 'The published mechanism has usable visual evidence',
            'decisive_limit': 'The experiment establishes a possible route, not prevalence',
            'visual_plan': [{'segment': 1, 'visual': 'Identified organism in its setting',
                             'purpose': 'Establish who and where before the mystery',
                             'source_or_concept': 'Correctly identified reference footage',
                             'accuracy_note': 'It is not footage of study animals'}],
        },
    }
    ep['editorial_review'] = review_record()
    ep['editorial_review']['source_sha256'] = editorial_source_sha256(ep, 'Evidence v1')
    return ep


class EditorialGates(unittest.TestCase):
    def test_changed_script_asset_or_evidence_invalidates_pre_render_review(self):
        ep = reviewed_episode()
        self.assertTrue(validate_pre_render(ep, 'Evidence v1'))
        script = copy.deepcopy(ep)
        script['production']['segments'][0]['speech'] = 'A different claim.'
        asset = copy.deepcopy(ep)
        asset['production']['assets'][0]['url'] = 'https://example.org/reference-b.mp4'
        for changed in (script, asset):
            with self.assertRaisesRegex(AssertionError, 'stale'):
                validate_pre_render(changed, 'Evidence v1')
        with self.assertRaisesRegex(AssertionError, 'stale'):
            validate_pre_render(ep, 'Evidence v2')

    def test_new_episode_cannot_silently_use_legacy_gate(self):
        ep = reviewed_episode()
        del ep['production']['editorial_standard']
        with self.assertRaisesRegex(AssertionError, 'mandatory'):
            validate_pre_render(ep, 'Evidence v1')
        ep['id'] = 'TT-003'
        self.assertIsNone(validate_pre_render(ep, 'Evidence v1'))
        ep['publication_enabled'] = True
        with self.assertRaisesRegex(AssertionError, 'Rejected TT-003'):
            validate_pre_render(ep, 'Evidence v1')

    def test_missing_visual_segment_or_placeholder_review_fails(self):
        ep = reviewed_episode()
        ep['editorial_story']['visual_plan'][0]['segment'] = 2
        with self.assertRaisesRegex(AssertionError, 'every narration segment'):
            validate_pre_render(ep, 'Evidence v1')
        ep = reviewed_episode()
        ep['editorial_review']['checks']['payoff']['finding'] = 'checked'
        with self.assertRaisesRegex(AssertionError, 'Incomplete'):
            validate_pre_render(ep, 'Evidence v1')

    def test_final_review_requires_exact_export_and_independent_review(self):
        manifest = {
            'editorial_style': 'science-journalism', 'editorial_standard': STANDARD,
            'editorial_source_sha256': 'source', 'fingerprint': 'render',
            'files': {'media/movie.mp4': 'video-sha', 'media/cover.jpg': 'cover-sha'},
            'evidence_sha256': 'evidence', 'script_author': 'script author',
        }
        final = review_record()
        final.update(source_sha256='source', fingerprint='render',
                     files=copy.deepcopy(manifest['files']), evidence_sha256='evidence',
                     independent_from_script_author=True, reviewed_encoded_frames=True)
        release = {'final_editorial_review': final}
        self.assertTrue(final_editorial_ok(release, manifest))
        for key in ('source_sha256', 'fingerprint', 'files', 'evidence_sha256'):
            changed = copy.deepcopy(release)
            changed['final_editorial_review'][key] = 'changed'
            self.assertFalse(final_editorial_ok(changed, manifest))
        for key in ('independent_from_script_author', 'reviewed_encoded_frames'):
            changed = copy.deepcopy(release)
            changed['final_editorial_review'][key] = False
            self.assertFalse(final_editorial_ok(changed, manifest))
        release['final_editorial_review']['reviewer'] = 'script author'
        self.assertFalse(final_editorial_ok(release, manifest))

    def test_old_journalism_review_cannot_release_rejected_pilot(self):
        self.assertFalse(final_editorial_ok(
            {'narrative_review': 'A nonempty review is insufficient'},
            {'editorial_style': 'science-journalism'}))


if __name__ == '__main__':
    unittest.main()
