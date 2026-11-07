"""Future Toxic Tales films: the real logo and clean, readable story frames.

The approved nature-story-8 renderer is frozen. This module changes composition
without changing that module or copying its audio/encode/QA pipeline. The copied
function's private global mapping replaces only Visuals and VERSION; importing
or running this renderer cannot rebind nature-story-8's globals.
"""
import base64
import hashlib
import io
import json
import types
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw
import production_nature as nature

ROOT = Path(__file__).resolve().parents[1]
Voice = nature.Voice
VERSION = 'nature-branded-9.0'
DECLARED_RENDERER = 'nature-branded-9'
BRANDING_STANDARD = 'toxic-tales-branding-v1'
BRAND_ASSET_PATH = ROOT / 'assets/branding/toxic-tales-logo.json'
LOGO_BOX = (82, 72, 140, 140)


def load_brand_logo(path=BRAND_ASSET_PATH):
    """Decode the archived original brand image and fail on missing provenance.

    The JSON envelope permits a byte-exact binary asset to travel through the
    repository's text-only publishing connector. No live avatar URL is fetched
    during rendering. The image bytes and their provenance are fingerprinted.
    """
    path = Path(path)
    record = json.loads(path.read_text(encoding='utf-8'))
    for key in ('source_url', 'owner', 'permission', 'sha256', 'data_base64'):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError('Missing brand asset provenance: ' + key)
    if record.get('schema_version') != 1:
        raise ValueError('Unsupported brand asset schema')
    if record.get('owner') != 'Toxic Tales / Akshay Mohan':
        raise ValueError('Brand asset must identify the approved account owner')
    raw = base64.b64decode(record['data_base64'], validate=True)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != record['sha256']:
        raise ValueError('Brand asset bytes do not match the pinned SHA-256')
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        if source.width != source.height or min(source.size) < 128:
            raise ValueError('Use the clean square/circular brand master at >=128px')
        dimensions = list(source.size)
        image = source.convert('RGBA')
    if record.get('dimensions') != dimensions:
        raise ValueError('Brand asset dimensions do not match its record')
    receipt = {k: v for k, v in record.items() if k != 'data_base64'}
    receipt.update({'archived_asset': 'assets/branding/toxic-tales-logo.json',
                    'download_sha256': digest,
                    'display_box_xywh': list(LOGO_BOX),
                    'changes': 'Uniform resize and circular display mask on the dark background; original logo identity and archived image bytes retained.'})
    return image, receipt


class Visuals(nature.Visuals):
    def __init__(self, ep, out, preview=False):
        # Check the mandatory brand asset before any font/media network work.
        image, self.brand_receipt = load_brand_logo()
        self.logo = image.resize(LOGO_BOX[2:], Image.Resampling.LANCZOS)
        mask = Image.new('L', (560, 560), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 559, 559), fill=255)
        mask = mask.resize(LOGO_BOX[2:], Image.Resampling.LANCZOS)
        self.logo.putalpha(ImageChops.multiply(self.logo.getchannel('A'), mask))
        super().__init__(ep, out, preview)

    def brand(self, image):
        image.paste(self.logo, LOGO_BOX[:2], self.logo)
        return image

    def frame(self, shot, t, caption='', progress=0):
        # Compose fresh from imagery/figures: never paint over a footer from v8.
        # progress remains an interface argument for the frozen encode pipeline.
        local = max(0, t - shot['start'])
        duration = max(.01, shot['end'] - shot['start'])
        phase = nature.clamp(local / duration)
        kind = shot['kind']
        photo = kind in ('portrait', 'closing', 'nature') or (kind == 'winter' and bool(shot.get('asset')))
        image = (self.gradient_photo(shot['asset'], local + shot.get('offset', 0), shot.get('focus'))
                 if photo else self.diagram(kind, local, phase, shot))
        if photo and shot.get('inset_cell'):
            layer = Image.new('RGBA', (nature.W, nature.H))
            ImageDraw.Draw(layer).ellipse((704, 958, 1036, 1290), fill=(4, 24, 31, 225), outline=(160, 210, 211, 110), width=2)
            image = Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')
            self.cell(image, 870, 1124, 102, local, True, True, 1, False)
            self.type.text(image, 'Cell illustration', 870, 1330, 22, nature.MUTED, weight=500, anchor='mm')
        self.brand(image)
        if shot.get('kicker'):
            self.type.text(image, shot['kicker'].upper(), 82, 240, 26, nature.ICE, weight=700)
        self.type.block(image, shot.get('title', ''), 78, 295, shot.get('title_size', 82), nature.PAPER,
                        width=910, face='display', weight=600, leading=1.06, max_lines=3)
        if shot.get('subtitle'):
            self.type.block(image, shot['subtitle'], 82, shot.get('subtitle_y', 490), 33,
                            nature.MUTED, width=900, weight=500, max_lines=2)
        if caption:
            lines = self.type.wrap(caption, 59, 874, 'sans', 650)
            if len(lines) > 2:
                raise ValueError('Caption needs shorter phrase: ' + caption)
            top = 1510 - (len(lines) - 1) * 33
            layer = Image.new('RGBA', (nature.W, nature.H))
            ImageDraw.Draw(layer).rounded_rectangle((66, top - 27, 1014, top + len(lines) * 75 + 25),
                                                    radius=24, fill=(3, 17, 22, 220))
            image = Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')
            for index, line in enumerate(lines):
                self.type.text(image, line, 540, top + index * 75, 59, nature.PAPER, weight=650, anchor='mt')
        # No wordmark substitute, FIELD NOTES, episode code, shot.note, source or
        # method fine print, or decorative progress line is drawn in this frame.
        return image

    def cover(self):
        plan = self.ep['production']
        image = self.gradient_photo(plan['cover_asset'], 0, plan.get('cover_focus'))
        self.brand(image)
        first_shot = plan['segments'][0]['shots'][0]
        kicker = plan.get('cover_kicker', first_shot.get('kicker', ''))
        if kicker:
            self.type.text(image, kicker.upper(), 82, 270, 27, nature.ICE, weight=750)
        title = plan.get('cover_title')
        if not title:
            raise ValueError('Future Reel requires a story-specific cover_title')
        self.type.block(image, title, 74, 335, 112, nature.PAPER, width=920,
                        face='display', weight=600, leading=1.02, max_lines=4)
        if plan.get('cover_subtitle'):
            self.type.block(image, plan['cover_subtitle'], 82, 1490, 46, nature.PAPER,
                            width=880, weight=600, max_lines=2)
        return image

    # Companion carousel composition deliberately remains the approved v8
    # design, including its useful scientific labels and readable source page.


def render(ep, voice, out):
    if ep.get('production', {}).get('renderer') != DECLARED_RENDERER:
        raise ValueError('Branded renderer requires an explicit nature-branded-9 declaration')
    # Each call gets a private globals mapping; neither the frozen module nor a
    # concurrent v8 render can observe these substitutions.
    namespace = dict(nature.render.__globals__)
    namespace.update(Visuals=Visuals, VERSION=VERSION)
    pipeline = types.FunctionType(nature.render.__code__, namespace, 'render_branded_pipeline',
                                  nature.render.__defaults__, nature.render.__closure__)
    result = pipeline(ep, voice, out)
    _, receipt = load_brand_logo()
    result.update(renderer=VERSION, declared_renderer=DECLARED_RENDERER,
                  branding_standard=BRANDING_STANDARD, brand_asset=receipt,
                  branding_layout={'logo_visible_from_opening': True,
                                   'logo_box_xywh': list(LOGO_BOX),
                                   'production_footer': False, 'progress_bar': False,
                                   'field_notes_or_episode_code': False,
                                   'scientific_labels_and_speech_captions': True},
                  branding_review_required=True, branding_review_claimed=False)
    return result
