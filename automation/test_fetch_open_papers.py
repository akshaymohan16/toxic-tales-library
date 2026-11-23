"""Offline boundaries for unattended open full-text access."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import fetch_open_papers as access

PAPER = {'pmcid': 'PMC4895153', 'expected_doi': '10.1038/srep27523'}


def article(doi=PAPER['expected_doi'], pmcid='4895153', licence='https://creativecommons.org/licenses/by/4.0/', body=None):
    if body is None:
        body = '<sec><title>Methods</title><p>' + ('Controlled observations and experimental controls. ' * 20) + '</p></sec><sec><title>Results</title><p>Observed evidence.</p></sec>'
    return ('''<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article" xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
<article-id pub-id-type="pmc">''' + pmcid + '''</article-id><article-id pub-id-type="doi">''' + doi + '''</article-id>
<title-group><article-title>Test original research</article-title></title-group>
<permissions><license xlink:href="''' + licence + '''"><license-p>Creative Commons Attribution</license-p></license></permissions>
</article-meta></front><body>''' + body + '''</body><back><ref-list><ref>Original reference.</ref></ref-list></back></article>''').encode()


def request(papers=None):
    return {'repository': access.REPOSITORY, 'request_id': 'test-request', 'papers': papers or [dict(PAPER)]}


class OpenPaperAccessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.root = self.base / 'repo'
        self.output = self.base / 'output'
        (self.root / 'automation').mkdir(parents=True)
        self.save_request(request())

    def save_request(self, data):
        (self.root / access.REQUEST).write_text(json.dumps(data), encoding='utf-8')

    def test_valid_identity_sections_and_review_not_implied(self):
        parsed, metadata = access.parse_article(article(), PAPER)
        self.assertEqual(metadata['sections'], ['Methods', 'Results'])
        self.assertFalse(metadata['scientific_review_complete'])
        self.assertIn('Check each proposed visual asset licence separately', metadata['required_before_selection'])
        self.assertIn('Original reference.', access.text(parsed))

    def test_mismatched_doi_and_pmcid_rejected(self):
        for raw in (article(doi='10.1234/wrong'), article(pmcid='2719796')):
            with self.assertRaisesRegex(ValueError, 'does not match'):
                access.parse_article(raw, PAPER)

    def test_html_abstract_only_and_dtd_entities_rejected(self):
        for raw in (b'<html><body>Login required</body></html>', article(body='Abstract only'),
                    b'<!DOCTYPE article [<!ENTITY injected "wrong">]>' + article(),
                    article().replace(b'<article ', b'<!DOCTYPE article SYSTEM "http://example.com/a.dtd"><article ', 1)):
            with self.assertRaises(ValueError):
                access.parse_article(raw, PAPER)

    def test_restrictive_and_missing_article_licences_rejected(self):
        for licence in ('https://creativecommons.org/licenses/by-nc/4.0/',
                        'https://creativecommons.org/licenses/by-nd/4.0/',
                        'https://creativecommons.org/licenses/by-sa/4.0/', '',
                        'https://untrusted.example/licenses/by/4.0/'):
            with self.assertRaisesRegex(ValueError, 'licence'):
                access.parse_article(article(licence=licence), PAPER)

    def test_cc_by_historical_versions_and_cc0_accepted(self):
        for licence in ('http://creativecommons.org/licenses/by/2.5/',
                        'https://creativecommons.org/licenses/by/3.0/',
                        'https://creativecommons.org/publicdomain/zero/1.0/'):
            _, meta = access.parse_article(article(licence=licence), PAPER)
            self.assertEqual(meta['license_urls'], [licence])

    def test_request_count_identity_and_untrusted_url_boundaries(self):
        invalid = [dict(request(), papers=[]), dict(request(), repository='other/repo'),
                   dict(request(), request_id=123), dict(request(), extra='bad'),
                   request([dict(PAPER), dict(PAPER)]),
                   request([dict(PAPER, url='https://example.com')]),
                   request([dict(PAPER, pmcid='../../secrets')])]
        invalid.append(request([{'pmcid': 'PMC' + str(i + 1), 'expected_doi': '10.1234/' + str(i)} for i in range(21)]))
        for value in invalid:
            with self.assertRaises(ValueError):
                access.validate_request(value)

    def test_fetch_writes_attributed_exact_xml_and_readable_text(self):
        raw = article()
        with patch.object(access, 'download', return_value=raw) as mocked:
            report = access.fetch_request(self.root, self.output)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(report['papers'][0]['status'], 'cached')
        folder = self.output / 'research/fulltext/PMC4895153'
        self.assertEqual((folder / 'article.xml').read_bytes(), raw)
        metadata = access.read_json(folder / 'metadata.json')
        self.assertEqual(metadata['xml_sha256'], access.digest(raw))
        readable = (folder / 'article.txt').read_text(encoding='utf-8')
        self.assertIn('Source API: https://www.ebi.ac.uk/', readable)
        self.assertIn('Original reference.', readable)
        self.assertIn('Methods', readable)
        self.assertEqual(access.verify_cache(self.output, PAPER)['title'], 'Test original research')

    def test_valid_cache_reuses_without_download_and_corruption_does_not_overwrite(self):
        with patch.object(access, 'download', return_value=article()):
            access.fetch_request(self.root, self.output)
        import shutil
        shutil.copytree(self.output / 'research', self.root / 'research')
        with patch.object(access, 'download', side_effect=AssertionError('No network')):
            report = access.fetch_request(self.root, self.base / 'second')
        self.assertEqual(report['papers'][0]['status'], 'reused')
        target = self.root / 'research/fulltext/PMC4895153/article.txt'
        target.write_text('Tampered', encoding='utf-8')
        with patch.object(access, 'download', side_effect=AssertionError('Do not silently repair')):
            report = access.fetch_request(self.root, self.base / 'third')
        self.assertEqual(report['papers'][0]['status'], 'skipped')
        self.assertIn('hash mismatch', report['papers'][0]['reason'])
        self.assertEqual(target.read_text(), 'Tampered')

    def test_official_fallback_and_skipped_candidate_are_reported(self):
        with patch.object(access, 'download', side_effect=[ValueError('Unavailable'), article()]) as download:
            report = access.fetch_request(self.root, self.output)
        self.assertEqual(report['papers'][0]['status'], 'cached')
        self.assertEqual(download.call_args_list[1].args[0], access.sources(PAPER['pmcid'])[1])
        with patch.object(access, 'download', side_effect=ValueError('Unavailable')):
            report = access.fetch_request(self.root, self.base / 'unavailable')
        self.assertEqual(report['papers'][0]['status'], 'skipped')
        self.assertFalse(report['scientific_review_complete'])

    def test_oai_wrapper_uses_exact_article_identity(self):
        wrapped = b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><GetRecord><record><metadata>' + article().split(b'?>', 1)[1] + b'</metadata></record></GetRecord></OAI-PMH>'
        _, metadata = access.parse_article(wrapped, PAPER)
        self.assertEqual(metadata['pmcid'], PAPER['pmcid'])

    def test_staging_cannot_modify_repository(self):
        with self.assertRaisesRegex(ValueError, 'outside repository'):
            access.fetch_request(self.root, self.root / 'output')


if __name__ == '__main__':
    unittest.main()
