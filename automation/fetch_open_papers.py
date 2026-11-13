"""Retrieve licence-eligible PMC full text through official APIs, without browser downloads.

Retrieval is an access check, never scientific review or publication approval.
Only a validated request can write a small, attributed public text cache.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'akshaymohan16/toxic-tales-library'
REQUEST = 'automation/paper-retrieval-request.json'
REPORT = 'automation/paper-retrieval-report.json'
MAX_BYTES = 5_000_000
PMCID = re.compile(r'PMC[1-9][0-9]{0,11}')
DOI = re.compile(r'10\.[0-9]{4,9}/[^\s<>"\\]+', re.I)
LAST_REQUEST = 0.0


def digest(data):
    return hashlib.sha256(data).hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_request(value):
    if (not isinstance(value, dict) or set(value) != {'repository', 'request_id', 'papers'}
            or value['repository'] != REPOSITORY
            or not isinstance(value['request_id'], str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', value['request_id'])
            or not isinstance(value['papers'], list) or not 1 <= len(value['papers']) <= 20):
        raise ValueError('Invalid paper retrieval request')
    seen = set()
    dois = set()
    for paper in value['papers']:
        if (not isinstance(paper, dict) or set(paper) != {'pmcid', 'expected_doi'}
                or not PMCID.fullmatch(str(paper['pmcid']))
                or not DOI.fullmatch(str(paper['expected_doi']))
                or paper['pmcid'] in seen or paper['expected_doi'].lower() in dois):
            raise ValueError('Invalid or duplicate paper identity')
        seen.add(paper['pmcid'])
        dois.add(paper['expected_doi'].lower())
    return value


def name(element):
    return element.tag.rsplit('}', 1)[-1]


def all_named(element, tag):
    return [child for child in element.iter() if name(child) == tag]


def text(element):
    return ' '.join(' '.join(element.itertext()).split())


def parse_article(raw, paper):
    if len(raw) > MAX_BYTES or re.search(br'<!\s*(?:DOCTYPE|ENTITY)', raw, re.I):
        raise ValueError('Oversized XML or forbidden document declaration')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('Response is not valid full-text XML') from exc
    if name(root).lower() == 'html' or all_named(root, 'error'):
        raise ValueError('API returned an error or HTML')
    articles = [root] if name(root) == 'article' else all_named(root, 'article')
    if len(articles) != 1:
        raise ValueError('Expected exactly one article')
    article = articles[0]
    fronts = [x for x in article if name(x) == 'front']
    bodies = [x for x in article if name(x) == 'body']
    if len(fronts) != 1 or len(bodies) != 1 or len(text(bodies[0])) < 500:
        raise ValueError('Complete substantial article body is unavailable')
    front = fronts[0]
    ids = all_named(front, 'article-id')
    pmc_ids = {re.sub(r'^PMC', '', text(x), flags=re.I) for x in ids
               if x.attrib.get('pub-id-type', '').lower() in ('pmc', 'pmcid')}
    doi_ids = {text(x).lower() for x in ids if x.attrib.get('pub-id-type', '').lower() == 'doi'}
    if pmc_ids != {paper['pmcid'][3:]} or doi_ids != {paper['expected_doi'].lower()}:
        raise ValueError('Requested PMCID or DOI does not match full text')
    titles = all_named(front, 'article-title')
    if len(titles) != 1 or not text(titles[0]):
        raise ValueError('Article title unavailable')
    licences = all_named(front, 'license')
    licence_urls = set()
    for licence in licences:
        values = list(licence.attrib.values()) + [text(licence)]
        values += [value for child in licence.iter() for value in child.attrib.values()]
        for value in values:
            for found in re.findall(r'https?://creativecommons\.org/[^\s<>"\')]+', value, re.I):
                licence_urls.add(found.rstrip('.,;'))
    allowed = re.compile(r'https?://creativecommons\.org/(?:licenses/by/[1-4]\.0|licenses/by/2\.5|publicdomain/zero/1\.0)/?(?:legalcode|deed\.[a-z-]+)?/?$', re.I)
    if not licence_urls or any(not allowed.fullmatch(url) for url in licence_urls):
        raise ValueError('Public cache requires unambiguous article-level CC BY or CC0 licence')
    licence_text = ' '.join(text(x) for x in licences)
    if re.search(r'non[- ]?commercial|no[- ]?derivatives|share[- ]?alike|CC[- ]BY[- ](?:NC|ND|SA)', licence_text, re.I):
        raise ValueError('Article licence has excluded restrictions')
    sections = [text(x) for x in all_named(bodies[0], 'title')]
    if not sections:
        raise ValueError('Full-text section structure unavailable')
    return article, {
        'pmcid': paper['pmcid'], 'doi': paper['expected_doi'].lower(),
        'title': text(titles[0]), 'article_type': article.attrib.get('article-type'),
        'license_urls': sorted(licence_urls), 'license_statement': licence_text,
        'body_characters': len(text(bodies[0])), 'sections': sections,
        'supplement_links': [dict(x.attrib) for x in all_named(article, 'supplementary-material')],
        'scientific_review_complete': False,
        'required_before_selection': ['Read original study and necessary supplements',
            'Check current correction, retraction and expression-of-concern records',
            'Confirm peer review, study design, claims and limitations',
            'Check each proposed visual asset licence separately'],
        'cache_scope': 'Article XML and text only; no PDF, figure or supplementary asset download. Cached access is not editorial approval.'}


def readable(article, metadata):
    blocks = {'article-title', 'title', 'p', 'sec', 'abstract', 'ref', 'table-wrap',
              'caption', 'list-item', 'contrib', 'body', 'front', 'back'}
    def walk(node):
        value = node.text or ''
        for child in node:
            value += walk(child) + (child.tail or '')
        return ('\n' + value + '\n') if name(node) in blocks else value
    body = '\n'.join(' '.join(line.split()) for line in walk(article).splitlines() if line.strip())
    header = '\n'.join([
        metadata['title'], 'DOI: ' + metadata['doi'], 'PMCID: ' + metadata['pmcid'],
        'Source API: ' + metadata['source_url'], 'Retrieved: ' + metadata['retrieved_at'],
        'Licence: ' + ', '.join(metadata['license_urls']),
        'XML SHA256: ' + metadata['xml_sha256'],
        'Text extraction from licensed JATS XML; layout changed, article wording retained.',
        'Access verified only. Scientific review, current notices and asset rights still require checks.', ''])
    return (header + '\n' + body + '\n').encode('utf-8')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('API redirect is not permitted')


def download(url):
    global LAST_REQUEST
    for attempt in range(3):
        time.sleep(max(0, 1.0 - (time.monotonic() - LAST_REQUEST)))
        LAST_REQUEST = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={
                'User-Agent': 'ToxicTalesOpenPaperAccess/1.0', 'Accept-Encoding': 'gzip',
                'Accept': 'application/xml,text/xml'})
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=25) as response:
                if response.geturl() != url:
                    raise ValueError('API changed its authorised URL')
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError('Response exceeds fixed size limit')
                if response.headers.get('Content-Encoding', '').lower() == 'gzip':
                    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as zipped:
                        raw = zipped.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError('Expanded response exceeds fixed size limit')
                return raw
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ValueError('API HTTP status ' + str(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 2:
                raise ValueError('API connection unavailable') from exc
        time.sleep(attempt + 1)


def sources(pmcid):
    return [
        'https://www.ebi.ac.uk/europepmc/webservices/rest/' + pmcid + '/fullTextXML',
        'https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/?' + urllib.parse.urlencode({
            'verb': 'GetRecord', 'identifier': 'oai:pubmedcentral.nih.gov:' + pmcid[3:], 'metadataPrefix': 'pmc'})]


def cache_path(root, pmcid):
    target = Path(root) / 'research/fulltext' / pmcid
    if not PMCID.fullmatch(pmcid) or target.resolve() != target.absolute():
        raise ValueError('Unsafe cache path')
    return target


def verify_cache(root, paper):
    folder = cache_path(root, paper['pmcid'])
    if not folder.exists():
        return None
    if not folder.is_dir() or any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('Unsafe existing cache')
    metadata = read_json(folder / 'metadata.json')
    xml = (folder / 'article.xml').read_bytes()
    extracted = (folder / 'article.txt').read_bytes()
    _, checked = parse_article(xml, paper)
    if (metadata.get('xml_sha256') != digest(xml) or metadata.get('text_sha256') != digest(extracted)
            or metadata.get('doi') != checked['doi'] or metadata.get('pmcid') != checked['pmcid']
            or metadata.get('source_url') not in sources(paper['pmcid'])):
        raise ValueError('Existing cache identity or hash mismatch; retained for investigation')
    return metadata


def fetch_request(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError('Staging output must be outside repository')
    if os.environ.get('GITHUB_REPOSITORY', REPOSITORY) != REPOSITORY:
        raise ValueError('Repository mismatch')
    raw_request = (root / REQUEST).read_bytes()
    request = validate_request(json.loads(raw_request))
    report = {'repository': REPOSITORY, 'request_id': request['request_id'],
              'request_sha256': digest(raw_request), 'checked_at': utcnow(),
              'scientific_review_complete': False, 'papers': []}
    for paper in request['papers']:
        result = dict(paper)
        try:
            cached = verify_cache(root, paper)
            if cached:
                result.update(status='reused', xml_sha256=cached['xml_sha256'], title=cached['title'])
            else:
                failures = []
                for source in sources(paper['pmcid']):
                    try:
                        raw = download(source)
                        article, metadata = parse_article(raw, paper)
                        metadata.update(source_url=source, retrieved_at=utcnow(), xml_sha256=digest(raw))
                        fulltext = readable(article, metadata)
                        metadata['text_sha256'] = digest(fulltext)
                        folder = cache_path(output, paper['pmcid'])
                        folder.mkdir(parents=True, exist_ok=True)
                        (folder / 'article.xml').write_bytes(raw)
                        (folder / 'article.txt').write_bytes(fulltext)
                        (folder / 'metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                        result.update(status='cached', source_url=source, xml_sha256=metadata['xml_sha256'], title=metadata['title'])
                        break
                    except (ValueError, OSError) as exc:
                        failures.append(str(exc))
                else:
                    result.update(status='skipped', reason='; '.join(failures))
        except (ValueError, OSError, KeyError) as exc:
            result.update(status='skipped', reason=str(exc))
        report['papers'].append(result)
    destination = output / REPORT
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


def persist_output(root, output):
    """Fast-forward only; never replace a changed request or a concurrent cache entry."""
    root, output = Path(root).resolve(), Path(output).resolve()
    report = read_json(output / REPORT)
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or report.get('repository') != REPOSITORY:
        raise ValueError('Persistence is restricted to the authorised GitHub repository')
    def git(*args, check=True):
        return subprocess.run(['git', *args], cwd=root, check=check, text=True, capture_output=True)
    git('config', 'user.name', 'github-actions[bot]')
    git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    for attempt in range(3):
        git('fetch', 'origin', 'main')
        git('checkout', '-B', 'paper-cache-update', 'refs/remotes/origin/main')
        if digest((root / REQUEST).read_bytes()) != report['request_sha256']:
            return {'status': 'superseded_request_not_committed'}
        allowed = [output / REPORT]
        for item in report['papers']:
            if item['status'] == 'cached':
                paper = {'pmcid': item['pmcid'], 'expected_doi': item['expected_doi']}
                verify_cache(output, paper)
                folder = cache_path(output, item['pmcid'])
                allowed.extend(folder / filename for filename in ('article.xml', 'article.txt', 'metadata.json'))
        relative_paths = []
        for source in allowed:
            relative = source.relative_to(output)
            destination = root / relative
            if destination.is_symlink() or destination.resolve() != destination.absolute():
                raise ValueError('Unsafe persistence path')
            if str(relative).replace('\\', '/') != REPORT and destination.exists() and destination.read_bytes() != source.read_bytes():
                raise ValueError('Concurrent cache change retained; fetch a fresh request')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            relative_paths.append(relative.as_posix())
        git('add', '--', *relative_paths)
        if git('diff', '--cached', '--quiet', check=False).returncode == 0:
            return {'status': 'already_current'}
        git('commit', '-m', 'Cache licensed open full text for ' + report['request_id'])
        if git('push', 'origin', 'HEAD:main', check=False).returncode == 0:
            return {'status': 'committed', 'commit': git('rev-parse', 'HEAD').stdout.strip()}
        # A concurrent main update is resolved by rebuilding only this cache commit.
        time.sleep(attempt + 1)
    raise ValueError('Concurrent updates prevented a safe fast-forward cache commit')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--persist', action='store_true')
    options = parser.parse_args()
    result = persist_output(ROOT, options.output) if options.persist else fetch_request(ROOT, options.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
