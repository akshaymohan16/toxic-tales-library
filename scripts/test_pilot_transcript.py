"""Critical spoken claims tolerate ASR spelling, never missing claim qualifiers."""
import json, unittest
from pathlib import Path
from production_pilot import ROOT, critical_tokens, require_critical_terms, validate_text_layout


class PilotTranscriptGates(unittest.TestCase):
    def test_three_digit_and_word_are_equivalent(self):
        require_critical_terms('After incubation, 3 hatched.', ['Three hatched'])
        require_critical_terms('After incubation, three hatched.', ['3 hatched'])

    def test_eight_digit_and_word_are_equivalent(self):
        require_critical_terms('They fed eggs to 8 mallards.', ['eight mallards'])
        require_critical_terms('They fed eggs to eight mallards.', ['8 mallards'])

    def test_punctuation_and_case_do_not_change_claim(self):
        require_critical_terms('Water—and incubated. It DID NOT show establishment.',
                               ['water and incubated', 'did not show'])

    def test_all_supported_numbers_keep_token_order(self):
        self.assertEqual(critical_tokens('one two three four five six seven eight nine ten eleven twelve'),
                         critical_tokens('1 2 3 4 5 6 7 8 9 10 11 12'))

    def test_missing_negation_fails(self):
        for transcript in ('It did show a wild population.', 'It showed no wild population.'):
            with self.subTest(transcript=transcript), self.assertRaises(ValueError):
                require_critical_terms(transcript, ['did not show'])

    def test_missing_or_changed_qualifier_fails(self):
        for transcript in ('An egg survived.', 'An egg will survive.'):
            with self.subTest(transcript=transcript), self.assertRaises(ValueError):
                require_critical_terms(transcript, ['could survive'])

    def test_exact_adjacent_tokens_required(self):
        for transcript in ('thirteen hatched', 'three almost hatched', 'three eggs hatched'):
            with self.subTest(transcript=transcript), self.assertRaises(ValueError):
                require_critical_terms(transcript, ['three hatched'])

    @unittest.skipUnless(Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf').exists(),
                         'Exact production DejaVu font is available on the Linux renderer')
    def test_every_pilot_caption_and_headline_fits_production_font(self):
        for path in sorted((ROOT/'episodes').glob('*.json')):
            episode=json.loads(path.read_text(encoding='utf-8'))
            if episode.get('production',{}).get('renderer')=='ecology-story-7':
                with self.subTest(episode=episode['id']):validate_text_layout(episode)

    def test_layout_preflight_rejects_caption_overflow(self):
        episode={'production':{'segments':[{'captions':['A very long subtitle phrase with many extra words that cannot possibly fit in two readable lines.'],'shots':[]}]}}
        with self.assertRaises(ValueError):validate_text_layout(episode)


if __name__=='__main__':
    unittest.main()
