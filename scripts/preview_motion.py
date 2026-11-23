"""Render a reviewed, approved story privately; never create a release or post."""
import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

import build
import build_motion
import production_motion as motion
from editorial_gate import validate_pre_render
from preserve_releases import historical_story

ROOT = Path(__file__).resolve().parents[1]


def prepare(episode_path, output_dir):
    output = Path(output_dir).resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError('Preview output must be outside the production repository/site/cache')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty output directory; previews never overwrite earlier exports')
    ep = json.loads(Path(episode_path).read_text(encoding='utf-8'))
    if ep.get('publication_enabled') is not False or ep.get('posts') != []:
        raise ValueError('Preview must have publication disabled and no posts')
    original_path = ROOT / 'episodes' / (ep['id'].lower() + '.json')
    if not original_path.resolve().is_relative_to(ROOT / 'episodes'):
        raise ValueError('Invalid preview episode identity')
    original_path, original, evidence, approved, _ = historical_story(ROOT, ep['id'])
    if ep.get('slug') != original.get('slug'):
        raise ValueError('Preview must retain the approved story slug')
    approved = approved or {}
    original_source = validate_pre_render(original, evidence.read_text(encoding='utf-8'))
    original_fp = build.render_fingerprint(original_path, evidence, build.select_renderer(original), original_source)
    if approved.get('decision') != 'release' or approved.get('fingerprint') != original_fp:
        raise ValueError('The preview must use a currently verified approved source story')
    for key in ('doi', 'evidence_file', 'evidence', 'editorial_story', 'slides'):
        if ep.get(key) != original.get(key):
            raise ValueError('Preview changed approved story content: ' + key)
    old_segments, new_segments = original['production']['segments'], ep['production']['segments']
    if len(old_segments) != len(new_segments):
        raise ValueError('Preview changed approved segment count')
    for old, new in zip(old_segments, new_segments):
        if old['speech'] != new['speech'] or old['captions'] != new['captions']:
            raise ValueError('Preview changed approved narration or captions')
    build.validate(ep)
    source = validate_pre_render(ep, evidence.read_text(encoding='utf-8'))
    motion.validate_motion_spec(ep)
    return ep, output, source, original_fp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    path = Path(args.episode).resolve()
    ep, output, source, original_fp = prepare(path, args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    media, qa = output / 'media', output / 'qa'
    voice = motion.Voice()
    with tempfile.TemporaryDirectory(prefix='toxic-tales-motion-') as temporary:
        manifest = motion.render(ep, voice, Path(temporary), media_dir=media, qa_dir=qa)
    files = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(media.iterdir()) if p.is_file()}
    video = media / (ep['slug'] + '.mp4')
    info = json.loads(motion.nature.sh(['ffprobe', '-v', 'error', '-count_frames',
                        '-show_streams', '-show_format', '-of', 'json', video]).stdout)
    vs = next(s for s in info['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    if ((vs['width'], vs['height']) != (1080, 1920) or vs['avg_frame_rate'] != '24/1'
            or vs['pix_fmt'] != 'yuv420p' or audio['codec_name'] != 'aac'
            or int(audio['sample_rate']) != 48000 or audio['channels'] != 2):
        raise ValueError('Encoded preview format gate failed')
    if abs(float(vs['duration']) - float(audio['duration'])) > .1:
        raise ValueError('Encoded audio/video duration drift exceeds 100 ms')
    if int(vs['nb_read_frames']) < math.floor(float(audio['duration']) * 24) - 1:
        raise ValueError('Encoded preview lost video frames')
    # Decode transition middles and settled titles, in addition to inherited
    # opening/boundary/shot/final QA. Review these actual encoded frames.
    transition_frames = []
    for i, shot in enumerate(manifest['shots']):
        for label, offset in [('transition', .18), ('settled', .7)]:
            seek = min(shot['end'] - 1 / 24, shot['start'] + offset)
            frame = qa / f'shot-{i+1:02}-{label}.jpg'
            motion.nature.sh(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                             '-ss', str(seek), '-i', video, '-frames:v', '1',
                             '-vf', 'scale=540:960', frame])
            transition_frames.append(frame.relative_to(output).as_posix())
    manifest.update(publication_enabled=False, release_eligible=False,
                    preview_of_approved_fingerprint=original_fp,
                    editorial_standard='story-first-v1', editorial_source_sha256=source,
                    script_author=ep.get('script_author', 'Toxic Tales production editor'),
                    evidence_sha256=hashlib.sha256((ROOT / ep['evidence_file']).read_bytes()).hexdigest(),
                    fingerprint=build_motion.render_fingerprint(path, ROOT / ep['evidence_file'], motion, source),
                    files=files, transition_midpoint_frames=transition_frames,
                    encoded_format=info, independent_export_release_claimed=False)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'preview': str(video), 'manifest': str(output / 'manifest.json'),
                      'technical_passed': True, 'publication_enabled': False,
                      'release_eligible': False}, indent=2))


if __name__ == '__main__':
    main()
