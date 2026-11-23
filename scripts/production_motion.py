"""Deterministic motion for future, independently reviewed Toxic Tales films.

This layer owns only picture composition. It reuses the existing neural voice,
alignment, encoder, transcript/loudness gates and exact-export QA in an isolated
function namespace. Published renderers and their module globals stay frozen.
No network provider, scheduler, publication state or approval is added here.
"""
import copy
import hashlib
import json
import math
import types
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

import production_branded as branded
import production_nature as nature
from motion_spec import validate_motion_spec

Voice = nature.Voice
VERSION = 'nature-motion-10.0'
DECLARED_RENDERER = 'nature-motion-10'
MOTION_STANDARD = 'toxic-tales-motion-v1'
TRANSITION_SECONDS = .36
FONT_HASHES = {
    'sans': ('d0639be45d0af36e798172419d7bd173c4bd4f29e2b76cbb69db1d11bf8b0a40',
             'e01b637272e0cbdfb240184dd98ea5cc671556d9894dae2668d92ab2c906787c'),
    'display': ('177ff6c0f14e5550a3c624247cd1189611d4eb65d000b14944c63d967958abbb',
                'bdf4c22802eaf804f998195871c6b8938aac2ac14b2d78a8bd66a6f1eced833b'),
}
STUDY_FRAME_RECIPE = 'ffmpeg-fps8-scale1280x720-jpeg-q3-v1'


def ease(value):
    """Quintic easing: zero velocity and acceleration at either endpoint."""
    value = max(0., min(1., float(value)))
    return value * value * value * (value * (value * 6 - 15) + 10)


def validate_aligned_timeline(shots, duration):
    """Reject gaps, overlaps, empty coverage and nonfinite voice timing."""
    def finite(value):
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    if not finite(duration) or duration <= 0:
        raise ValueError('Motion narration duration must be positive and finite')
    cursor = 0.
    for shot in shots:
        start, end = shot.get('start'), shot.get('end')
        if (not finite(start) or not finite(end) or abs(start - cursor) > 1e-5
                or end <= start or end > duration + 1e-5):
            raise ValueError('Motion requires a contiguous aligned shot timeline')
        cursor = end
    if not shots or abs(cursor - duration) > 1e-5:
        raise ValueError('Motion timeline must cover the exact narration duration')


def decode_study_frames(source, out):
    """Reuse extracted footage only after a complete, hash-verified decode.

    A failed decoder never writes the completion receipt. Partial or altered
    frame caches are removed and rebuilt solely inside this render's output.
    """
    source_sha = nature.sha(source)
    out = Path(out).resolve()
    folder = out / ('study-frames-' + source_sha[:20])
    folder.mkdir(parents=True, exist_ok=True)
    if not folder.resolve().is_relative_to(out):
        raise ValueError('Study frame cache escapes the render output')
    marker = folder / 'complete.json'
    frames = sorted(folder.glob('frame_*.jpg'))
    def frame_records():
        records = []
        for path in frames:
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Study frame escapes its content-addressed cache')
            records.append({'name': path.name, 'sha256': nature.sha(path)})
        return records
    expected = {'schema_version': 1, 'source_sha256': source_sha,
                'recipe': STUDY_FRAME_RECIPE, 'frames': frame_records()}
    if marker.is_file():
        try:
            if frames and json.loads(marker.read_text(encoding='utf-8')) == expected:
                return frames
        except (ValueError, OSError):
            pass
    # Every deletion is a single known generated file within the checked folder.
    for path in [*frames, marker]:
        if path.exists():
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Study frame cache file escapes the render output')
            path.unlink()
    nature.sh(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
               '-i', source, '-vf', 'fps=8,scale=1280:720', '-q:v', '3',
               folder / 'frame_%04d.jpg'])
    frames = sorted(folder.glob('frame_*.jpg'))
    if not frames:
        raise ValueError('No actual frames extracted from licensed study footage')
    for path in frames:
        with Image.open(path) as image:
            image.verify()
    expected['frames'] = frame_records()
    temporary_marker = folder / 'complete.tmp'
    temporary_marker.write_text(json.dumps(expected, sort_keys=True) + '\n', encoding='utf-8')
    temporary_marker.replace(marker)
    return frames


class Typography(nature.Typography):
    """The same pinned OFL fonts, with preview-local license notices."""
    def __init__(self, artifact_root=None):
        self.paths = {}
        self.receipts = []
        self.preview = False
        license_dir = (Path(artifact_root) if artifact_root else nature.ROOT / 'site') / 'licenses'
        license_dir.mkdir(parents=True, exist_ok=True)
        for spec in nature.FONT_SPECS:
            font_sha, license_sha = FONT_HASHES[spec['id']]
            path = nature.download(spec['url'], nature.CACHE / 'fonts' / spec['filename'], font_sha)
            license_path = nature.download(spec['license_url'], nature.CACHE / 'fonts' /
                                           (spec['family'] + '-4024282-OFL.txt'), license_sha)
            public_license = license_dir / (spec['family'] + '-OFL.txt')
            public_license.write_bytes(license_path.read_bytes())
            self.paths[spec['id']] = path
            self.receipts.append({**spec, 'download_sha256': nature.sha(path),
                                  'license_sha256': nature.sha(license_path),
                                  'archived_license': 'licenses/' + public_license.name,
                                  'upstream_commit': '4024282d9b0cffcdb8e3024560862746178d741f'})


class Visuals(branded.Visuals):
    """Random-access picture evaluation; identical inputs/time produce one frame.

    The timeline supplies the preceding shot for an artwork-only transition. No
    previous-frame state, wall clock, unseeded randomness or frame order is used.
    Logo, headline and captions are composed once after the artwork transition.
    """
    def __init__(self, ep, out, preview=False, *, timeline=None, artifact_root=None):
        if preview:
            raise ValueError('Motion previews require the real pinned fonts and licensed assets')
        self.motion_receipt = validate_motion_spec(ep)
        self.timeline = timeline if timeline is not None else []
        self._camera_masters = {}
        image, self.brand_receipt = branded.load_brand_logo()
        self.logo = image.resize(branded.LOGO_BOX[2:], Image.Resampling.LANCZOS)
        mask = Image.new('L', (560, 560), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 559, 559), fill=255)
        mask = mask.resize(branded.LOGO_BOX[2:], Image.Resampling.LANCZOS)
        self.logo.putalpha(ImageChops.multiply(self.logo.getchannel('A'), mask))

        # Clone only the initialization namespace so Typography can archive its
        # licenses beside an unpublished preview without writing into site/.
        visual_ep = copy.deepcopy(ep)
        clips = [a for a in visual_ep['production']['assets'] if a.get('media_type') == 'video/webm']
        visual_ep['production']['assets'] = [a for a in visual_ep['production']['assets'] if a not in clips]
        namespace = dict(nature.Visuals.__init__.__globals__)
        namespace['Typography'] = lambda unused=False: Typography(artifact_root)
        initialize = types.FunctionType(nature.Visuals.__init__.__code__, namespace,
                                        'initialize_motion_visuals', nature.Visuals.__init__.__defaults__)
        initialize(self, visual_ep, out, False)
        self.ep = ep
        self.study_video_paths = {}
        for asset in clips:
            source = nature.download(asset['url'], nature.CACHE / 'assets' /
                                     (hashlib.sha256(asset['url'].encode()).hexdigest()[:12] + '-' + asset['filename']),
                                     asset.get('sha256'))
            self.assets[asset['id']] = source
            self.study_video_paths[asset['id']] = decode_study_frames(source, out)

    def photograph(self, key, t=0, focus=None, size=(nature.W, nature.H)):
        """Gentle editorial pan/push on a real still; never fabricated footage."""
        if key not in self.photos:
            raise ValueError('Missing required licensed photograph: ' + str(key))
        focus = tuple(focus or self.info[key].get('focus', [.5, .5]))
        cache_key = (key, focus, tuple(size))
        if cache_key not in self._camera_masters:
            self._camera_masters[cache_key] = ImageOps.fit(
                self.photos[key], (math.ceil(size[0] * 1.12), math.ceil(size[1] * 1.12)),
                Image.Resampling.LANCZOS, centering=focus)
        master = self._camera_masters[cache_key]
        phase = ease(max(0, t) / 8.)
        zoom = 1.025 + .045 * phase
        width = master.width / zoom
        height = master.height / zoom
        # Bounded movement retains the chosen subject focus and fills the frame.
        left = (master.width - width) * (.28 + .44 * phase)
        top = (master.height - height) * (.68 - .30 * phase)
        return master.resize(size, Image.Resampling.LANCZOS,
                             box=(left, top, left + width, top + height))

    def evidence_count(self, shot, local):
        metric = shot['motion']['metric']
        value, total = metric['value'], metric['total']
        # Defense in depth, including direct frame callers bypassing render().
        if (isinstance(value, bool) or isinstance(total, bool)
                or not isinstance(value, int) or not isinstance(total, int)
                or not 0 <= value <= total <= 30 or total < 1):
            raise ValueError('Evidence count requires integer 0 <= value <= total <= 30')
        image = self.background.copy()
        self.type.block(image, metric['label'], 540, 660, 42, nature.ICE,
                        width=900, weight=600, anchor='mt', max_lines=2)
        # Numerical text is always the exact verified result. Only the visual
        # emphasis arrives in sequence; intermediate counts are never printed.
        self.type.text(image, f'{value} of {total}', 540, 835, 115, nature.PAPER,
                       face='display', anchor='mm')
        self.type.text(image, metric['unit'], 540, 935, 39, nature.MUTED, anchor='mm')
        columns = min(total, 10)
        rows = math.ceil(total / columns)
        spacing = min(146, 870 / columns)
        radius = min(46, spacing * .32)
        d = ImageDraw.Draw(image)
        for i in range(total):
            col, row = i % columns, i // columns
            row_count = min(columns, total - row * columns)
            x = 540 + (col - (row_count - 1) / 2) * spacing
            y = 1050 + row * 85
            d.ellipse((x - radius, y - radius, x + radius, y + radius),
                      fill='#173638', outline=nature.MUTED, width=2)
            arrive = ease((local - .18 - i * min(.10, 1.2 / total)) / .4)
            if i < value and arrive:
                rr = radius * .83 * arrive
                d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=nature.MINT)
        self.type.block(image, metric['scope'], 540, max(1200, 1105 + (rows - 1) * 85), 33,
                        nature.MUTED, width=890, anchor='mt', max_lines=2)
        self.type.text(image, 'Animated reveal · not a time series', 540, 1400, 29,
                       nature.MUTED, weight=500, anchor='mm')
        return image

    def diagram(self, kind, t, p, shot=None):
        shot = shot or {}
        if kind == 'evidence_count':
            return self.evidence_count(shot, t)
        image = super().diagram(kind, t, p, shot)
        d = ImageDraw.Draw(image)
        if kind == 'spider_oxygen':
            # Qualitative direction of oxygen exchange; not molecule counts,
            # speed, concentration, a flux model, or observed experimental data.
            for side in (-1, 1):
                for row in range(4):
                    q = (t * .32 + row * .23) % 1
                    x = (170 + q * 145) if side < 0 else (915 - q * 155)
                    y = 890 + row * 105 + 12 * q
                    rr = 4 + 2 * math.sin(q * math.pi)
                    d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=nature.MINT)
        elif kind == 'bee_rolling':
            # Rotation cue on the existing conceptual wooden ball. Its path is
            # illustrative, never presented as a measured study trajectory.
            center = 500 + int(55 * math.sin(t * .6))
            angle = t * .6
            for j in range(3):
                a = angle + j * math.tau / 3
                d.line((center, 1038, center + 92 * math.cos(a), 1038 + 92 * math.sin(a)),
                       fill='#e8bd7f', width=4)
        return image

    def artwork(self, shot, t):
        local = max(0, t - shot['start'])
        duration = max(.01, shot['end'] - shot['start'])
        kind = shot['kind']
        photo = kind in ('portrait', 'closing', 'nature') or (kind == 'winter' and bool(shot.get('asset')))
        image = (self.gradient_photo(shot['asset'], local + shot.get('offset', 0), shot.get('focus'))
                 if photo else self.diagram(kind, local, nature.clamp(local / duration), shot))
        if photo and shot.get('inset_cell'):
            layer = Image.new('RGBA', (nature.W, nature.H))
            ImageDraw.Draw(layer).ellipse((704, 958, 1036, 1290), fill=(4, 24, 31, 225),
                                           outline=(160, 210, 211, 110), width=2)
            image = Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')
            self.cell(image, 870, 1124, 102, local, True, True, 1, False)
            self.type.text(image, 'Cell illustration', 870, 1330, 22, nature.MUTED,
                           weight=500, anchor='mm')
        return image

    def transition(self, image, shot, t):
        local = max(0, t - shot['start'])
        if local >= TRANSITION_SECONDS or not self.timeline:
            return image
        previous = next((item for item in reversed(self.timeline)
                         if item['start'] < shot['start'] and abs(item['end'] - shot['start']) < 1e-5), None)
        if previous is None:
            return image
        old = self.artwork(previous, max(previous['start'], previous['end'] - 1 / nature.FPS))
        if 'evidence_count' in (previous['kind'], shot['kind']):
            # Never wipe through a numerical claim: a spatial mask can briefly
            # turn "11 of 13" into "11 of 1" or leave an isolated denominator.
            # Fade every pixel of the old claim together to neutral, then every
            # pixel of the new claim together from neutral. The two claims are
            # never blended with each other, even for adjacent count scenes.
            half = TRANSITION_SECONDS / 2
            if local < half:
                return Image.blend(old, self.background, ease(local / half))
            return Image.blend(self.background, image, ease((local - half) / half))
        phase = ease(local / TRANSITION_SECONDS)
        edge = -64 + phase * (nature.W + 128)
        # Only a narrow feather overlaps art; words in the captions/headline
        # and the canonical logo are never blended, shifted or duplicated.
        values = bytes(round(255 * nature.clamp((edge - x + 32) / 64)) for x in range(nature.W))
        mask = Image.frombytes('L', (nature.W, 1), values).resize((nature.W, nature.H))
        return Image.composite(image, old, mask)

    def headline(self, image, shot, local):
        size = shot.get('title_size', 82)
        lines = self.type.wrap(shot.get('title', ''), size, 910, 'display', 600)
        if len(lines) > 3:
            raise ValueError('Title exceeds motion safe area')
        if shot.get('kicker'):
            self.type.text(image, shot['kicker'].upper(), 82, 240, 26, nature.ICE, weight=700)
        layer = Image.new('RGBA', image.size)
        for index, line in enumerate(lines):
            # Staggered lines settle in <0.7s. The opening text is already
            # legible, without a typewriter delay or bouncing captions.
            arrival = ease((local - index * .075) / .42)
            y = 295 + index * size * 1.06 + 22 * (1 - arrival)
            opacity = round(255 * (.45 + .55 * arrival))
            ink = nature.rgba(nature.PAPER, opacity)
            bounds = ImageDraw.Draw(layer).textbbox((78, y), line,
                                                   font=self.type.font(size, 'display', 600), anchor='lt')
            if bounds[2] > 1000:
                raise ValueError('Title contains a word outside the safe area')
            self.type.text(layer, line, 78, y, size, ink, face='display', weight=600)
        image = Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')
        if shot.get('subtitle'):
            self.type.block(image, shot['subtitle'], 82, shot.get('subtitle_y', 490), 33,
                            nature.MUTED, width=900, weight=500, max_lines=2)
        return image

    def caption(self, image, caption):
        if not caption:
            return image
        lines = self.type.wrap(caption, 59, 874, 'sans', 650)
        if len(lines) > 2:
            raise ValueError('Caption needs shorter phrase: ' + caption)
        top = 1510 - (len(lines) - 1) * 33
        layer = Image.new('RGBA', (nature.W, nature.H))
        ImageDraw.Draw(layer).rounded_rectangle((66, top - 27, 1014, top + len(lines) * 75 + 25),
                                                radius=24, fill=(3, 17, 22, 220))
        image = Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')
        for index, line in enumerate(lines):
            self.type.text(image, line, 540, top + index * 75, 59, nature.PAPER,
                           weight=650, anchor='mt')
        return image

    def frame(self, shot, t, caption='', progress=0):
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError('Motion frame time must be finite')
        image = self.transition(self.artwork(shot, t), shot, t)
        image = self.headline(image, shot, max(0, t - shot['start']))
        self.brand(image)
        return self.caption(image, caption)


def render(ep, voice, out, *, media_dir=None, qa_dir=None):
    """Run the proven production gates with new pictures, optionally off-site.

    Supplying both destinations isolates previews from public media and QA. A
    successful render remains unapproved: the independent exact-export reviews
    and SHA-based release gate must be satisfied by the existing producer.
    """
    if ep.get('production', {}).get('renderer') != DECLARED_RENDERER:
        raise ValueError('Motion renderer requires an explicit nature-motion-10 declaration')
    receipt = validate_motion_spec(ep)
    if (media_dir is None) != (qa_dir is None):
        raise ValueError('Preview requires both media_dir and qa_dir')
    media = Path(media_dir) if media_dir is not None else nature.MEDIA
    qa = Path(qa_dir) if qa_dir is not None else nature.QA
    timeline = []

    class BoundVisuals(Visuals):
        def __init__(self, episode, output):
            super().__init__(episode, output, timeline=timeline,
                             artifact_root=media.parent if media_dir is not None else None)

    class AlignedVoice:
        asr = voice.asr

        def make(self, episode, output):
            result = voice.make(episode, output)
            shots, captions, audit, duration = result
            validate_aligned_timeline(shots, duration)
            timeline.extend(shots)
            return result

    namespace = dict(nature.render.__globals__)
    namespace.update(Visuals=BoundVisuals, VERSION=VERSION, MEDIA=media, QA=qa)
    pipeline = types.FunctionType(nature.render.__code__, namespace, 'render_motion_pipeline',
                                  nature.render.__defaults__, nature.render.__closure__)
    result = pipeline(ep, AlignedVoice(), out)
    _, brand_receipt = branded.load_brand_logo()
    result.update(renderer=VERSION, declared_renderer=DECLARED_RENDERER,
                  motion=receipt, motion_standard=MOTION_STANDARD,
                  motion_spec_sha256=receipt['spec_sha256'],
                  motion_provenance={'engine': 'pillow-ffmpeg', 'deterministic': True,
                                     'paid_services': False, 'spec_sha256': receipt['spec_sha256']},
                  motion_review_required=True, motion_review_claimed=False,
                  branding_standard=branded.BRANDING_STANDARD, brand_asset=brand_receipt,
                  branding_layout={'logo_visible_from_opening': True,
                                   'logo_box_xywh': list(branded.LOGO_BOX),
                                   'production_footer': False, 'progress_bar': False,
                                   'field_notes_or_episode_code': False,
                                   'scientific_labels_and_speech_captions': True},
                  branding_review_required=True, branding_review_claimed=False,
                  representation=('Licensed source images/footage and source-specific conceptual ecological '
                                  'illustrations; editorial camera moves and staged evidence reveals. '
                                  'Animation timing is not a measured time series or experimental simulation.'),
                  motion_features={'kinetic_titles': 'quintic staggered-line entrance',
                                   'transitions': ('0.36-second artwork transition; count scenes fade through neutral '
                                                   'without slicing or overlapping numerals, other scenes use a '
                                                   'feathered wipe; captions and logo remain single'),
                                   'camera': 'bounded editorial pan and push on licensed stills',
                                   'data': 'exact verified labels; animated count emphasis only',
                                   'timebase': 'aligned narration seconds at 24 frames per second'})
    return result
