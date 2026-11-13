"""Compact exact-export review material; never a publication approval.

This additive helper owns only review outputs for new production episodes. It
leaves every source, release, encoded video and original renderer QA unchanged.
"""
import argparse
import hashlib
import html
import json
import math
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image

import build_current as current
import preserve_current_releases as preserve_current
from editorial_gate import editorial_source_sha256
from motion_spec import motion_spec_sha256

ROOT = Path(__file__).resolve().parents[1]
FROZEN_EPISODES = current.frozen_motion.FROZEN_LEGACY_EPISODES
MAX_PACKAGE_BYTES = 50_000_000


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def contained(root, relative):
    """Accept canonical repository-relative POSIX paths, including on Windows."""
    if (not isinstance(relative, str) or '\\' in relative
            or ':' in relative or relative.startswith('/')
            or any(part in {'', '.', '..'} for part in relative.split('/'))):
        raise ValueError('Unsafe review input path')
    target = (root / PurePosixPath(relative)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Review input escapes its allowed directory')
    return target


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def episode_stem(episode_id):
    if (not isinstance(episode_id, str) or not re.fullmatch(r'TT-\d{3,}', episode_id)
            or episode_id in FROZEN_EPISODES):
        raise ValueError('Review outputs are scoped to canonical nonfrozen episode IDs')
    return episode_id.lower()


def review_output(qa, name, episode_id):
    stem = episode_stem(episode_id)
    pattern = re.escape(stem) + r'-review(?:-shot-\d{2,3}-plus-(?:018|070)\.jpg|-index\.json|\.zip|\.html)'
    if not re.fullmatch(pattern, name):
        raise ValueError('Output is outside scoped review filenames')
    target = qa / name
    if target.is_symlink() or target.resolve() != target.absolute():
        raise ValueError('Review output must not redirect through a symbolic link')
    return target


def extract_frame(video, target, when):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-ss', format(when, '.6f'), '-i', str(video), '-frames:v', '1',
                    '-vf', 'scale=540:960', '-q:v', '3', str(target)],
                   check=True, capture_output=True, text=True)


def verified_image(path, dimensions=None):
    with Image.open(path) as image:
        if image.format != 'JPEG' or (dimensions and image.size != dimensions):
            raise ValueError('Unexpected encoded review image geometry or format')
        image.verify()


def released(root, episode_id):
    path = contained(root, 'quality/releases.json')
    releases = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    return releases.get(episode_id, {}).get('decision') == 'release'


def package_review(root=ROOT, episode_id='TT-008'):
    stem = episode_stem(episode_id)
    root = Path(root).resolve()
    if released(root, episode_id):
        result = dict(preserve_current.verify_released_local(root, episode_id))
        result.update(episode=episode_id, status='retained exact released review bytes')
        return result
    site = contained(root, 'site')
    qa = contained(site, 'qa')
    episode_path = contained(root, 'episodes/' + stem + '.json')
    episode = json.loads(episode_path.read_text(encoding='utf-8'))
    manifest_path = contained(site, 'qa/' + stem + '.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if episode.get('id') != episode_id or not episode.get('production'):
        raise ValueError('Review source identity or production is missing')
    renderer = current.select_renderer(episode)
    receipt = renderer.validate_motion_spec(episode)
    if (episode['production'].get('renderer') != renderer.DECLARED_RENDERER
            or manifest.get('declared_renderer') != renderer.DECLARED_RENDERER
            or manifest.get('renderer') != renderer.VERSION
            or manifest.get('motion') != receipt
            or manifest.get('scene_family') != receipt.get('scene_family')
            or manifest.get('scene_doi') != receipt.get('scene_doi')
            or manifest.get('technical_passed') is not True):
        raise ValueError('Review source and encoded manifest identities do not match')
    fingerprint = manifest.get('fingerprint', '')
    slug = episode.get('slug', '')
    if (not re.fullmatch(r'[0-9a-f]{64}', fingerprint)
            or not re.fullmatch(re.escape(stem) + r'-[a-z0-9-]+', slug)):
        raise ValueError('Invalid exact-export identity')
    evidence_path = contained(root, episode['evidence_file'])
    if not evidence_path.is_relative_to((root / 'evidence').resolve()):
        raise ValueError('Evidence path is outside evidence directory')
    if (manifest.get('evidence_sha256') != sha(evidence_path)
            or manifest.get('editorial_source_sha256') != editorial_source_sha256(
                episode, evidence_path.read_text(encoding='utf-8'))
            or manifest.get('motion_spec_sha256') != motion_spec_sha256(episode)):
        raise ValueError('Review manifest is stale relative to the source')
    media_stem = slug + '-' + fingerprint[:12]
    video_rel = 'media/' + media_stem + '.mp4'
    cover_rel = 'media/' + media_stem + '_cover.jpg'
    files = manifest.get('files', {})
    if not isinstance(files, dict):
        raise ValueError('Exact media file hashes are missing')
    # Validate every listed path before matching the exact two expected outputs.
    for relative in files:
        contained(site, relative)
    if set(files) != {video_rel, cover_rel}:
        raise ValueError('Expected exactly one Reel and one cover')
    for relative, expected in files.items():
        if not re.fullmatch(r'[0-9a-f]{64}', expected) or sha(contained(site, relative)) != expected:
            raise ValueError('Encoded media hash mismatch: ' + relative)
    video = contained(site, video_rel)
    cover = contained(site, cover_rel)
    verified_image(cover)
    duration = manifest.get('duration')
    shots = manifest.get('shots')
    if not number(duration) or duration <= 0 or not isinstance(shots, list) or not 1 <= len(shots) <= 100:
        raise ValueError('Invalid encoded shot timeline')
    cursor = 0.
    existing = [{'path': 'qa/' + stem + '-contact.jpg', 'role': 'contact sheet'}]
    for i, shot in enumerate(shots, 1):
        start, end = shot.get('start'), shot.get('end')
        if (not number(start) or not number(end) or abs(start - cursor) > 1e-5
                or end <= start or end > duration + 1e-5):
            raise ValueError('Invalid encoded shot coverage')
        cursor = end
        existing.append({'path': f'qa/{stem}-shot-{i:02}.jpg', 'role': 'shot midpoint',
                         'shot': i, 'time_seconds': (start + end) / 2})
        if i > 1:
            for side, when in (('before', max(0., start - 1 / 24)), ('after', start + 1 / 24)):
                existing.append({'path': f'qa/{stem}-boundary-{i-1:02}-{side}.jpg',
                                 'role': 'transition ' + side, 'shot': i, 'time_seconds': when})
    # Encoded duration may contain one final frame/audio packet of padding.
    if abs(cursor - duration) > .1:
        raise ValueError('Encoded shot timeline does not cover the film')
    existing.extend([
        {'path': f'qa/{stem}-opening-0s.jpg', 'role': 'opening', 'time_seconds': 0.},
        {'path': f'qa/{stem}-opening-1s.jpg', 'role': 'opening', 'time_seconds': 1.},
        {'path': f'qa/{stem}-final-frame.jpg', 'role': 'final encoded frame',
         'sampling_note': 'Renderer decoded its final one-second window and reversed it.'}])
    expected_boundary = {r['path'] for r in existing if r['role'] not in {'contact sheet', 'shot midpoint'}}
    if (manifest.get('contact_sheet') != existing[0]['path']
            or set(manifest.get('boundary_frame_checks', [])) != expected_boundary):
        raise ValueError('Encoded manifest does not identify the expected frame coverage')
    for record in existing:
        verified_image(contained(site, record['path']))
    # Stage all new files privately. No existing renderer QA file is overwritten.
    with tempfile.TemporaryDirectory(prefix=stem + '-review-', dir=qa) as temporary:
        staging = Path(temporary)
        generated = []
        for i, shot in enumerate(shots, 1):
            for offset, suffix in ((.18, '018'), (.7, '070')):
                when = min(shot['start'] + offset, max(shot['start'], shot['end'] - 1 / 48))
                name = f'{stem}-review-shot-{i:02}-plus-{suffix}.jpg'
                path = staging / name
                extract_frame(video, path, when)
                verified_image(path, (540, 960))
                generated.append({'path': 'qa/' + name, 'role': 'post-boundary sample',
                                  'shot': i, 'offset_seconds': offset, 'time_seconds': when})
        records = existing + generated
        members = {manifest_path.name: manifest_path, cover.name: cover}
        for record in existing:
            members[PurePosixPath(record['path']).name] = contained(site, record['path'])
        for record in generated:
            members[PurePosixPath(record['path']).name] = staging / PurePosixPath(record['path']).name
        index = {'schema_version': 1, 'episode_id': episode_id,
                 'status': 'review material only; no publication approval',
                 'fingerprint': fingerprint, 'video': {'path': video_rel, 'sha256': files[video_rel]},
                 'manifest': {'path': 'qa/' + manifest_path.name, 'sha256': sha(manifest_path)},
                 'source_episode_sha256': sha(episode_path), 'frames': records,
                 'files': {name: sha(path) for name, path in sorted(members.items())}}
        index_path = staging / (stem + '-review-index.json')
        index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        members['review-index.json'] = index_path
        if sum(path.stat().st_size for path in members.values()) >= MAX_PACKAGE_BYTES:
            raise ValueError('Review package exceeds compact size limit')
        archive = staging / (stem + '-review.zip')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, path in sorted(members.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                bundle.writestr(info, path.read_bytes())
        if archive.stat().st_size >= MAX_PACKAGE_BYTES:
            raise ValueError('Review archive exceeds compact size limit')
        cards = []
        for record in records:
            label = record['role'] + (f" - shot {record['shot']}" if 'shot' in record else '')
            if 'time_seconds' in record:
                label += f" - {record['time_seconds']:.3f}s"
            cards.append('<figure><a href="' + html.escape(PurePosixPath(record['path']).name) +
                         '"><img loading="lazy" src="' + html.escape(PurePosixPath(record['path']).name) +
                         '" alt="' + html.escape(label) + '"></a><figcaption>' +
                         html.escape(label) + '</figcaption></figure>')
        page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>' + episode_id + ' encoded export review</title><style>'
                'body{font:16px system-ui;background:#071c22;color:#edf4ed;margin:24px}'
                'a{color:#ade8d0}nav{display:flex;gap:22px;flex-wrap:wrap}'
                '.frames{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}'
                'figure{margin:0}img{max-width:100%;height:auto}figcaption{padding:8px 0}'
                'video{display:block;max-height:75vh;max-width:100%;margin:20px 0}'
                '</style><h1>' + episode_id + ' encoded export review</h1>'
                '<p>Exact encoded frames and source manifest. This page does not grant publication approval.</p>'
                '<nav><a href="' + stem + '-review.zip" download>Download review ZIP</a>'
                '<a href="../' + html.escape(video_rel) + '" download>Download original MP4</a>'
                '<a href="' + manifest_path.name + '">Export manifest</a>'
                '<a href="' + index_path.name + '">Review hashes and sample times</a></nav>'
                '<video controls preload="metadata" poster="../' + html.escape(cover_rel) +
                '" src="../' + html.escape(video_rel) + '"></video>'
                '<div class="frames">' + ''.join(cards) + '</div></html>')
        page_path = staging / (stem + '-review.html')
        page_path.write_text(page, encoding='utf-8')
        for record in generated:
            name = PurePosixPath(record['path']).name
            (staging / name).replace(review_output(qa, name, episode_id))
        for path in (index_path, archive, page_path):
            path.replace(review_output(qa, path.name, episode_id))
    return {'episode': episode_id, 'archive': 'qa/' + stem + '-review.zip',
            'page': 'qa/' + stem + '-review.html', 'frames': len(records),
            'video_sha256': files[video_rel]}


def package_current(root=ROOT):
    root = Path(root).resolve()
    results = []
    for source in sorted(contained(root, 'episodes').glob('*.json')):
        episode = json.loads(source.read_text(encoding='utf-8'))
        episode_id = episode.get('id')
        if not episode.get('production') or episode_id in FROZEN_EPISODES:
            continue
        stem = episode_stem(episode_id)
        if source.resolve() != contained(root, 'episodes/' + stem + '.json'):
            raise ValueError('Production episode source filename does not match its ID')
        if released(root, episode_id) or contained(root, 'site/qa/' + stem + '.json').is_file():
            results.append(package_review(root, episode_id))
    return results


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--episode')
    mode.add_argument('--current', action='store_true')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = package_current(args.root) if args.current else package_review(args.root, args.episode)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
