"""Restore exact current releases before build; never regenerate approved bytes."""
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, HTTPRedirectHandler, build_opener

from editorial_gate import validate_pre_render

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'akshaymohan16/toxic-tales-library'
SITE_URL = 'https://akshaymohan16.github.io/toxic-tales-library/'
LEGACY = frozenset('TT-%03d' % value for value in range(2, 8))
SHA256 = re.compile(r'[0-9a-f]{64}')
MAX_MEDIA_BYTES = 250_000_000
MAX_QA_BYTES = 20_000_000


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _read(path, default=None):
    if not path.exists() and default is not None:
        return default
    if path.stat().st_size > 8_000_000:
        raise ValueError('Oversized release JSON')
    return json.loads(path.read_text(encoding='utf-8'))


def _safe_path(root, relative, prefix=None):
    if (not isinstance(relative, str) or any(c in relative for c in '\\:?#')
            or any(p in ('', '.', '..') for p in relative.split('/'))
            or (prefix and not relative.startswith(prefix + '/'))):
        raise ValueError('Unsafe release path')
    target = root / relative
    if target.is_symlink() or target.resolve() != target.absolute() or not target.resolve().is_relative_to(root):
        raise ValueError('Release path escapes or redirects its repository')
    return target


def _load_pipeline(root, entrypoint):
    if not isinstance(entrypoint, str) or not re.fullmatch(r'scripts/build_[a-z0-9_]+\.py', entrypoint):
        raise ValueError('Invalid production entrypoint')
    path = _safe_path(root, entrypoint, 'scripts')
    if not path.is_file():
        raise ValueError('Production entrypoint missing')
    spec = importlib.util.spec_from_file_location('_preserved_current_pipeline', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not all(callable(getattr(module, name, None)) for name in ('select_renderer', 'render_fingerprint', 'release_ok')):
        raise ValueError('Production entrypoint lacks current release gates')
    if hasattr(module, 'build') and Path(module.build.ROOT).resolve() != root:
        raise ValueError('Production pipeline belongs to another repository root')
    return module


def _setup(root):
    config = _read(_safe_path(root, 'automation/config.json'))
    if (config.get('allowed_repository') != REPOSITORY or config.get('site_url') != SITE_URL
            or os.environ.get('GITHUB_REPOSITORY', REPOSITORY) != REPOSITORY):
        raise ValueError('Repository or authorised Pages origin mismatch')
    entrypoint = config.get('production_entrypoint')
    if not isinstance(entrypoint, str) or not re.fullmatch(r'scripts/build_[a-z0-9_]+\.py', entrypoint):
        raise ValueError('Invalid production entrypoint')
    _safe_path(root, entrypoint, 'scripts')
    releases = _read(_safe_path(root, 'quality/releases.json'))
    if not isinstance(releases, dict):
        raise ValueError('Malformed release map')
    identities = set()
    for path in sorted((root / 'episodes').glob('*.json')):
        _safe_path(root, path.relative_to(root).as_posix(), 'episodes')
        episode = _read(path)
        eid = episode.get('id') if isinstance(episode, dict) else None
        if (not isinstance(eid, str) or not re.fullmatch(r'TT-\d{3,}', eid)
                or eid in identities or path.name != eid.lower() + '.json'):
            raise ValueError('Duplicate or renamed production episode identity')
        identities.add(eid)
    return releases, _load_pipeline(root, entrypoint)


def _source_record(root, episode_id, release, pipeline):
    if not isinstance(episode_id, str) or not re.fullmatch(r'TT-\d{3,}', episode_id) or episode_id in LEGACY:
        raise ValueError('Invalid current release identity')
    path = _safe_path(root, 'episodes/' + episode_id.lower() + '.json')
    episode = _read(path)
    if episode.get('id') != episode_id or not episode.get('production'):
        raise ValueError('Missing or renamed released source')
    evidence = _safe_path(root, episode['evidence_file'], 'evidence')
    source = validate_pre_render(episode, evidence.read_text(encoding='utf-8'))
    renderer = pipeline.select_renderer(episode)
    fingerprint = pipeline.render_fingerprint(path, evidence, renderer, source)
    if (not SHA256.fullmatch(str(fingerprint)) or fingerprint != release.get('fingerprint')
            or sha(evidence) != release.get('evidence_sha256')
            or not SHA256.fullmatch(str(source))
            or release.get('source_sha256', source) != source
            or release.get('final_editorial_review', {}).get('source_sha256') != source):
        raise ValueError('Released source or dependency changed; refusing to rerender ' + episode_id)
    if not SHA256.fullmatch(str(release.get('encoded_review_index_sha256', ''))):
        raise ValueError('Released encoded review index hash is required')
    slug = episode.get('slug', '')
    if not re.fullmatch(re.escape(episode_id.lower()) + r'-[a-z0-9-]+', slug):
        raise ValueError('Unsafe released media slug')
    stem = slug + '-' + fingerprint[:12]
    expected = {'media/' + stem + '.mp4', 'media/' + stem + '_cover.jpg'}
    files = release.get('files', {})
    if not isinstance(files, dict) or set(files) != expected:
        raise ValueError('Released media inventory does not match its fingerprint')
    site = _safe_path(root, 'site')
    for relative, digest in files.items():
        _safe_path(site, relative, 'media')
        if not SHA256.fullmatch(str(digest)):
            raise ValueError('Invalid released media hash')
    return dict(id=episode_id, episode=episode, path=path, release=release, renderer=renderer,
                source=source, fingerprint=fingerprint, pipeline=pipeline)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise ValueError('Release archive redirects are forbidden')


def _open(request):
    return build_opener(_NoRedirect()).open(request, timeout=30)


def _download(relative, target, maximum):
    if not re.fullmatch(r'(?:qa|media)/[a-z0-9_.-]+', relative):
        raise ValueError('Unsafe archive download path')
    url = SITE_URL + quote(relative, safe='/')
    for attempt in range(3):
        try:
            with _open(Request(url, headers={'User-Agent': 'ToxicTalesExactCurrentArchive/1.0'})) as response:
                if response.geturl() != url:
                    raise ValueError('Release archive changed the exact authorised URL')
                size = 0
                with target.open('wb') as output:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        size += len(block)
                        if size > maximum:
                            raise ValueError('Release archive exceeds fixed size limit')
                        output.write(block)
            return
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def _index_files(root, record, index):
    episode_id, release = record['id'], record['release']
    stem = episode_id.lower()
    manifest_relative = 'qa/' + stem + '.json'
    media = release['files']
    video = next(p for p in media if p.endswith('.mp4'))
    manifest = index.get('manifest', {})
    if (index.get('episode_id') != episode_id or index.get('fingerprint') != record['fingerprint']
            or index.get('source_episode_sha256') != sha(record['path'])
            or index.get('video') != {'path': video, 'sha256': media[video]}
            or manifest.get('path') != manifest_relative
            or not SHA256.fullmatch(str(manifest.get('sha256', '')))):
        raise ValueError('Pinned review index source or media identity mismatch')
    files = index.get('files')
    if not isinstance(files, dict) or files.get(stem + '.json') != manifest['sha256']:
        raise ValueError('Pinned review index lacks exact QA manifest')
    inventory = dict(media)
    cover = next(p for p in media if p.endswith('_cover.jpg'))
    if files.get(Path(cover).name) != media[cover]:
        raise ValueError('Pinned review index cover hash mismatch')
    for name, digest in files.items():
        if not isinstance(name, str) or '/' in name or '\\' in name or not SHA256.fullmatch(str(digest)):
            raise ValueError('Unsafe pinned QA filename or hash')
        if name == Path(cover).name:
            continue
        if name != stem + '.json' and not re.fullmatch(re.escape(stem) + r'-[a-z0-9-]+\.jpg', name):
            raise ValueError('Pinned QA filename is outside its episode')
        relative = 'qa/' + name
        _safe_path(root / 'site', relative, 'qa')
        inventory[relative] = digest
    return inventory


def _manifest_ok(record, manifest):
    release = record['release']
    if (not isinstance(manifest, dict)
            or any(manifest.get(k) != release.get(k) for k in ('fingerprint', 'files', 'evidence_sha256'))
            or manifest.get('editorial_source_sha256') != record['source']
            or manifest.get('renderer') != record['renderer'].VERSION
            or not record['pipeline'].release_ok(release, manifest, record['episode'])):
        raise ValueError('Released QA manifest or review identity mismatch')


def verify_released_local(root, episode_id):
    """Read-only proof used before retaining an immutable review package."""
    root = Path(root).resolve()
    releases, pipeline = _setup(root)
    release = releases.get(episode_id, {})
    if release.get('decision') != 'release':
        raise ValueError('Episode has no current release')
    record = _source_record(root, episode_id, release, pipeline)
    relative = 'qa/' + episode_id.lower() + '-review-index.json'
    index_path = _safe_path(root / 'site', relative, 'qa')
    if not index_path.is_file() or sha(index_path) != release['encoded_review_index_sha256']:
        raise ValueError('Pinned local review index is missing or changed')
    index = _read(index_path)
    inventory = _index_files(root, record, index)
    for name, digest in inventory.items():
        path = _safe_path(root / 'site', name)
        if not path.is_file() or sha(path) != digest:
            raise ValueError('Pinned local release file is missing or changed: ' + name)
    _manifest_ok(record, _read(root / 'site/qa' / (episode_id.lower() + '.json')))
    return {'episode': episode_id, 'fingerprint': record['fingerprint'], 'status': 'retained exact released review'}


def preserve_current_releases(root=None):
    root = (Path(root) if root is not None else ROOT).resolve()
    releases, pipeline = _setup(root)
    # Complete all source/dependency checks before any network or cache writes.
    records = [_source_record(root, eid, release, pipeline)
               for eid, release in sorted(releases.items())
               if eid not in LEGACY and isinstance(release, dict) and release.get('decision') == 'release']
    if not records:
        return {'preserved_episodes': [], 'restored_files': 0}
    cache = _safe_path(root, 'render-cache')
    cache_index_path = _safe_path(cache, 'index.json')
    cache_index = _read(cache_index_path, {})
    if not isinstance(cache_index, dict):
        raise ValueError('Malformed render cache index')
    cache.mkdir(parents=True, exist_ok=True)
    staged = []
    with tempfile.TemporaryDirectory(prefix='preserve-current-', dir=cache) as temporary:
        stage = Path(temporary)
        for record in records:
            eid, release = record['id'], record['release']
            relative = 'qa/' + eid.lower() + '-review-index.json'
            index_path = _safe_path(root / 'site', relative, 'qa')
            if not index_path.is_file() or sha(index_path) != release['encoded_review_index_sha256']:
                index_path = stage / (eid + '-review-index.json')
                _download(relative, index_path, 8_000_000)
                if sha(index_path) != release['encoded_review_index_sha256']:
                    raise ValueError('Public review index hash mismatch')
                staged.append((index_path, _safe_path(root / 'site', relative, 'qa')))
            inventory = _index_files(root, record, _read(index_path))
            available = {}
            for number, (relative, digest) in enumerate(inventory.items()):
                destination = _safe_path(root / 'site', relative)
                local = destination
                if not destination.is_file() or sha(destination) != digest:
                    local = stage / (eid + '-file-' + str(number))
                    _download(relative, local, MAX_MEDIA_BYTES if relative.startswith('media/') else MAX_QA_BYTES)
                    if sha(local) != digest:
                        raise ValueError('Public released file hash mismatch: ' + relative)
                    staged.append((local, destination))
                available[relative] = local
            _manifest_ok(record, _read(available['qa/' + eid.lower() + '.json']))
            cache_index[eid] = record['fingerprint']
        # Install only after every release, pinned QA record and media verifies.
        for source, destination in staged:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
        output = stage / 'index.json'
        output.write_text(json.dumps(cache_index, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        output.replace(cache_index_path)
    return {'preserved_episodes': [r['id'] for r in records], 'restored_files': len(staged)}


if __name__ == '__main__':
    print(json.dumps(preserve_current_releases(), indent=2))
