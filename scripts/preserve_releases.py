"""Restore exact legacy exports on cold caches; never silently rerender them.

Only the authorised public Pages origin is read. All sources and downloaded
bytes must match the existing release record, including held/rejected history.
No release decision, post, provider receipt or publishing schedule is changed.
Ancillary QA JPEGs have no signed historical hash: their source, readability
and newly observed hashes are recorded separately from exact released media.
"""
import re
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlparse
from urllib.request import Request, HTTPRedirectHandler, build_opener

from PIL import Image

import build
from editorial_gate import validate_pre_render

SITE_URL = 'https://akshaymohan16.github.io/toxic-tales-library/'
SHA256 = re.compile(r'[0-9a-f]{64}')
MAX_MEDIA_BYTES = 250_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise ValueError('Archive redirects are refused; exact authorised URLs are required')


def _open(request):
    return build_opener(_NoRedirect()).open(request, timeout=60)


def _safe_path(root, relative, prefix):
    if (not isinstance(relative, str) or '\\' in relative
            or any(c in relative for c in ('?', '#', ':'))
            or PurePosixPath(relative).is_absolute()
            or any(p in ('', '.', '..') for p in relative.split('/'))
            or not relative.startswith(prefix + '/')):
        raise ValueError('Unsafe archive path: ' + str(relative))
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Archive path escaped its destination')
    return target


def _download(relative, target, maximum):
    request = Request(SITE_URL + quote(relative, safe='/'),
                      headers={'User-Agent': 'ToxicTalesExactArchive/1.0'})
    with _open(request) as response:
        final = urlparse(response.geturl())
        if (final.scheme != 'https' or final.netloc != 'akshaymohan16.github.io'
                or not final.path.startswith('/toxic-tales-library/')
                or final.query or final.fragment):
            raise ValueError('Archive download redirected outside the authorised Pages origin')
        size = 0
        with target.open('wb') as output:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > maximum:
                    raise ValueError('Archive download exceeds the fixed size limit')
                output.write(block)


def _manifest_ok(manifest, release, renderer, source_sha):
    if not isinstance(manifest, dict) or manifest.get('renderer') != renderer.VERSION:
        return False
    if any(manifest.get(k) != release.get(k) for k in ('fingerprint', 'files', 'evidence_sha256')):
        return False
    return not source_sha or manifest.get('editorial_source_sha256') == source_sha


def _qa_image_receipt(path, relative):
    if not path.is_file() or path.stat().st_size > 20_000_000:
        raise ValueError('Ancillary QA image missing or too large')
    with Image.open(path) as image:
        width, height = image.size
        if (image.format != 'JPEG' or not 1 <= width <= 4096
                or not 1 <= height <= 16384 or width * height > 40_000_000):
            raise ValueError('Invalid ancillary QA image dimensions or format')
        image.verify()
    with Image.open(path) as image:
        image.load()
    return {'source_url': SITE_URL + relative, 'sha256': build.sha(path),
            'bytes': path.stat().st_size, 'dimensions': [width, height],
            'historical_release_hash_verified': False,
            'verification': 'Authorised Pages download; readable JPEG; observed SHA-256, not a signed historical media hash'}


def preserve_legacy_releases(root=None):
    """Verify/stage all old exports before any install or legacy build call."""
    root = (Path(root) if root is not None else build.ROOT).resolve()
    site, cache = root / 'site', root / 'render-cache'
    if not all(path.resolve().is_relative_to(root) for path in (site, cache)):
        raise ValueError('Legacy cache or site directory escaped the repository')
    releases = build.read(root / 'quality/releases.json', {})
    index = build.read(cache / 'index.json', {})
    qa_observations = build.read(cache / 'legacy-qa-observations.json', {})
    if not isinstance(index, dict) or not isinstance(releases, dict):
        raise ValueError('Malformed legacy cache or release records')
    cache.mkdir(parents=True, exist_ok=True)
    staged, preserved, updated_index = [], [], dict(index)
    observations = {}
    with tempfile.TemporaryDirectory(prefix='preserve-', dir=cache) as temporary:
        stage = Path(temporary)
        for path in sorted((root / 'episodes').glob('*.json')):
            episode = build.read(path)
            if not episode.get('production') or episode['production'].get('renderer') == 'nature-motion-10':
                continue
            episode_id = episode['id']
            if not re.fullmatch(r'TT-\d{3,}', episode_id):
                raise ValueError('Unsafe legacy episode identity')
            release = releases.get(episode_id)
            if not isinstance(release, dict) or not SHA256.fullmatch(str(release.get('fingerprint', ''))):
                raise ValueError('No exact legacy release identity for ' + episode_id)
            evidence_path = _safe_path(root, episode['evidence_file'], 'evidence')
            source_sha = validate_pre_render(episode, evidence_path.read_text(encoding='utf-8'))
            renderer = build.select_renderer(episode)
            fingerprint = build.render_fingerprint(path, evidence_path, renderer, source_sha)
            if (fingerprint != release['fingerprint']
                    or build.sha(evidence_path) != release.get('evidence_sha256')):
                raise ValueError('Legacy source changed; refusing to rerender ' + episode_id)
            files = release.get('files')
            if not isinstance(files, dict) or not files:
                raise ValueError('Legacy exact-file inventory missing for ' + episode_id)
            destinations = {}
            for relative, expected in files.items():
                destination = _safe_path(site, relative, 'media')
                if not SHA256.fullmatch(str(expected)):
                    raise ValueError('Invalid legacy media hash for ' + episode_id)
                destinations[relative] = destination
            qa_relative = 'qa/' + episode_id.lower() + '.json'
            qa_path = _safe_path(site, qa_relative, 'qa')
            try:
                manifest = build.read(qa_path, {})
            except (ValueError, OSError):
                manifest = {}
            if not _manifest_ok(manifest, release, renderer, source_sha):
                downloaded_qa = stage / (episode_id + '-qa.json')
                _download(qa_relative, downloaded_qa, 5_000_000)
                manifest = build.read(downloaded_qa)
                if not _manifest_ok(manifest, release, renderer, source_sha):
                    raise ValueError('Public legacy QA identity mismatch for ' + episode_id)
                staged.append((downloaded_qa, qa_path))
            for number, (relative, destination) in enumerate(destinations.items()):
                expected = files[relative]
                if destination.is_file() and build.sha(destination) == expected:
                    continue
                downloaded = stage / (episode_id + '-' + str(number))
                _download(relative, downloaded, MAX_MEDIA_BYTES)
                if build.sha(downloaded) != expected:
                    raise ValueError('Public legacy media hash mismatch: ' + relative)
                staged.append((downloaded, destination))
            references = manifest.get('boundary_frame_checks', [])
            if not isinstance(references, list):
                raise ValueError('Malformed ancillary QA references for ' + episode_id)
            references = list(references)
            if manifest.get('contact_sheet'):
                references.append(manifest['contact_sheet'])
            for number, relative in enumerate(dict.fromkeys(references)):
                destination = _safe_path(site, relative, 'qa')
                if not re.fullmatch('qa/' + episode_id.lower() + r'-[a-z0-9-]+\.jpg', relative):
                    raise ValueError('Ancillary QA path is not an episode-specific JPEG')
                previous = qa_observations.get(relative) if isinstance(qa_observations, dict) else None
                receipt = None
                if previous and destination.is_file():
                    try:
                        observed = _qa_image_receipt(destination, relative)
                        if observed == previous:
                            receipt = observed
                    except (OSError, ValueError):
                        pass
                if receipt is None:
                    downloaded = stage / (episode_id + '-ancillary-' + str(number))
                    _download(relative, downloaded, 20_000_000)
                    receipt = _qa_image_receipt(downloaded, relative)
                    staged.append((downloaded, destination))
                observations[relative] = receipt
            updated_index[episode_id] = fingerprint
            preserved.append(episode_id)
        # Nothing is installed until every legacy source, QA record and media
        # byte has been verified. A failed preflight cannot start a build/deploy.
        for source, destination in staged:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
        if updated_index != index:
            temporary_index = cache / 'preserved-index.json'
            build.write(temporary_index, updated_index)
            temporary_index.replace(cache / 'index.json')
        if observations != qa_observations:
            temporary_observations = cache / 'preserved-qa-observations.json'
            build.write(temporary_observations, observations)
            temporary_observations.replace(cache / 'legacy-qa-observations.json')
    return {'preserved_episodes': preserved, 'restored_files': len(staged)}
