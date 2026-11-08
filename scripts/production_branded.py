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



# -- SOURCE-SPECIFIC ECOLOGY STORY SCENES -----------------------------
# New ecology subjects can share the pinned voice, typography and official
# logo without reusing wood-frog figures. The old published nature-8 export
# remains untouched. These are concept illustrations, never measured figures.
import copy
import math
import subprocess
from PIL import ImageOps, ImageFilter

_SOURCE_INIT = Visuals.__init__
_SOURCE_DIAGRAM = Visuals.diagram

def _subject_init(self, ep, out, preview=False):
    clips = [a for a in ep['production']['assets'] if a.get('media_type') == 'video/webm']
    if clips:
        visual_copy = copy.deepcopy(ep)
        visual_copy['production']['assets'] = [
            a for a in ep['production']['assets'] if a not in clips
        ]
    else:
        visual_copy = ep
    _SOURCE_INIT(self, visual_copy, out, preview)
    self.ep = ep
    self.study_video_paths = {}
    if clips:
        for a in clips:
            if preview:
                raise ValueError('Real study footage is required even for preview')
            source = nature.download(a['url'], nature.CACHE / 'assets' /
                                     (hashlib.sha256(a['url'].encode()).hexdigest()[:12] + '-' + a['filename']),
                                     a.get('sha256'))
            self.assets[a['id']] = source
            folder = Path(out) / ('frames_' + a['id'])
            folder.mkdir(parents=True, exist_ok=True)
            frames = sorted(folder.glob('frame_*.jpg'))
            if len(frames) < 10:
                for old in frames: old.unlink()
                subprocess.run([
                    'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-i', str(source), '-vf', 'fps=8,scale=1280:720',
                    '-q:v', '3', str(folder / 'frame_%04d.jpg')
                ], check=True)
                frames = sorted(folder.glob('frame_*.jpg'))
            if not frames:
                raise ValueError('No actual frames extracted from licensed study footage')
            self.study_video_paths[a['id']] = frames

def _arrow(d, x1, y1, x2, y2, colour, thick=6):
    d.line((x1,y1,x2,y2), fill=colour, width=thick)
    direction = math.atan2(y2-y1,x2-x1)
    a=direction+2.55; b=direction-2.55
    d.polygon([(x2,y2),
               (x2+23*math.cos(a),y2+23*math.sin(a)),
               (x2+23*math.cos(b),y2+23*math.sin(b))], fill=colour)

def _spider(d, x, y, z=1):
    # Explicitly simplified diagram icon; body and 8 legs, not anatomical data.
    d.ellipse((x-23*z,y-33*z,x+23*z,y+13*z), fill='#634b38',
              outline='#ddb487',width=max(2,int(3*z)))
    d.ellipse((x-15*z,y+3*z,x+15*z,y+30*z), fill='#a8774d')
    for side in (-1,1):
        for i in range(4):
            a = (i-1.5)*.40
            x0=x+side*18*z; y0=y+2*z+i*5*z
            x1=x+side*(38+17*i)*z; y1=y-12*z+i*10*z
            x2=x+side*(72+16*i)*z; y2=y+(-19+26*i)*z
            d.line([(x0,y0),(x1,y1),(x2,y2)],
                   fill='#d8c19c',width=max(2,int(4*z)))
    d.ellipse((x-9*z,y+19*z,x-5*z,y+23*z),fill='#091f29')
    d.ellipse((x+5*z,y+19*z,x+9*z,y+23*z),fill='#091f29')

def _bee(d, x, y, z=1):
    # Simple bee silhouette for explanatory diagrams. Not a depiction of a trial.
    d.ellipse((x-52*z,y-30*z,x+48*z,y+30*z), fill='#e9b65b',outline='#13191a',width=max(2,int(4*z)))
    for xx in (-24,15):
        d.rectangle((x+(xx-9)*z,y-27*z,x+(xx+5)*z,y+27*z), fill='#262628')
    d.ellipse((x+35*z,y-22*z,x+63*z,y+22*z),fill='#24272c')
    d.ellipse((x-10*z,y-53*z,x+35*z,y-15*z),
              fill='#b3d6db',outline='#d4eff4',width=max(2,int(2*z)))
    for side in (-1,1):
        for i in range(3):
            y0=y-9*z+i*11*z
            d.line((x-15*z,y0,x+(-46+i*8)*z,y+(35+i*7)*z),
                   fill='#242629',width=max(2,int(3*z)))
    for k in (-1,1):
        d.line((x+51*z,y-12*z,x+67*z,y+(-23+12*k)*z),
               fill='#202a29',width=max(2,int(2*z)))

def _water_bell(self, image, t, p, filled=1):
    from PIL import ImageDraw
    layer=Image.new('RGBA',image.size)
    d=ImageDraw.Draw(layer)
    # Water and emergent stems are general conceptual habitat, no measurements.
    d.rectangle((0,640,1080,1390),fill=(7,58,66,105))
    for x in (220,790):
        d.line((x,1390,x-38,790),fill=(70,136,108,210),width=18)
        for j in range(3):
            y=900+j*125
            d.ellipse((x-120,y-30,x+36,y+33),fill=(49,111,93,165))
    # An open-bottom, silk-supported air pocket.
    width=340*filled
    d.ellipse((540-width,765,540+width,1380),fill=(168,231,228,48),
              outline=(186,248,244,245),width=7)
    d.rectangle((540-width-6,1100,540+width+6,1390),fill=(9,45,54,25))
    for j in range(11):
        xx=540-width+j*width*2/10
        d.line((xx,970,xx+18*math.sin(j),1290),fill=(165,240,221,55),width=2)
    image.paste(Image.alpha_composite(image.convert('RGBA'),layer).convert('RGB'))
    _spider(ImageDraw.Draw(image),540,1080,1.22)

def _subject_diagram(self, kind, t, p, shot=None):
    shot=shot or {}
    if kind not in {'spider_bell','spider_oxygen','spider_probe','spider_gas',
                    'spider_scope','bee_rolling','bee_path','bee_choice',
                    'bee_age','bee_scope','bee_video'}:
        return _SOURCE_DIAGRAM(self,kind,t,p,shot)
    image=self.background.copy()
    d=ImageDraw.Draw(image)
    if kind.startswith('spider_'):
        if kind == 'spider_bell':
            _water_bell(self,image,t,p)
            self.type.text(image,'Silk-supported air bell',540,1350,35,nature.ICE,anchor='mm')
        elif kind == 'spider_oxygen':
            _water_bell(self,image,t,p)
            d=ImageDraw.Draw(image)
            for j in range(4):
                y=890+j*105
                _arrow(d,165,y,318,y+12,nature.ICE,6)
                _arrow(d,920,y,755,y+12,nature.ICE,6)
            self.type.text(image,'Dissolved oxygen',540,700,37,nature.ICE,anchor='mm')
            self.type.text(image,'enters the bell',540,1380,32,nature.PAPER,anchor='mm')
        elif kind == 'spider_probe':
            _water_bell(self,image,t,p)
            d=ImageDraw.Draw(image)
            d.line((870,680,670,940),fill='#d8e5db',width=14)
            d.ellipse((657,928,683,954),fill=nature.AMBER)
            self.type.text(image,'Oxygen-sensitive probe',540,695,36,nature.ICE,anchor='mm')
            self.type.text(image,'In a controlled aquarium',540,1400,32,nature.MUTED,anchor='mm')
        elif kind == 'spider_gas':
            # Deliberately qualitative, not a timed measured series.
            _water_bell(self,image,t,p,filled=.78-.22*p)
            self.type.text(image,'Some gas escapes over time',540,680,35,nature.ICE,anchor='mm')
            self.type.text(image,'Surface air still needed',540,1405,38,nature.AMBER,anchor='mm')
        elif kind == 'spider_scope':
            self.type.text(image,'LABORATORY CONDITIONS',540,700,29,nature.ICE,anchor='mm')
            self.type.block(image,'Warm, still water\nResting spiders',540,800,69,
                            nature.PAPER,width=900,face='display',anchor='mt',max_lines=3)
            self.type.block(image,'Active and wild conditions\nwere not fully tested.',540,1110,38,
                            nature.MUTED,width=850,anchor='mt',max_lines=3)
    elif kind == 'bee_video':
        key=shot.get('asset')
        frames=self.study_video_paths.get(key)
        if not frames:
            raise ValueError('Required actual study video not decoded: '+str(key))
        idx=int((max(0,t)+float(shot.get('offset',0))) * 8) % len(frames)
        with Image.open(frames[idx]) as source:
            still=source.convert('RGB')
        background=ImageOps.fit(still,(1080,1920),Image.Resampling.LANCZOS)
        background=background.filter(ImageFilter.GaussianBlur(42)).convert('RGBA')
        shade=Image.new('RGBA',(1080,1920),(2,16,19,130))
        image=Image.alpha_composite(background,shade).convert('RGB')
        # Explanatory wide inset: the authentic horizontal research footage
        # is intentionally not misrepresented as portrait footage in nature.
        shot_image=ImageOps.fit(still,(1030,710),Image.Resampling.LANCZOS,
                                centering=(.48,.52))
        image.paste(shot_image,(25,720))
        self.type.text(image,'Actual study footage',540,677,32,nature.ICE,anchor='mm')
    elif kind == 'bee_rolling':
        ball_x=500+int(55*math.sin(t*.6))
        d.ellipse((ball_x-118,920,ball_x+118,1156),fill='#c99856',outline='#edc685',width=5)
        _bee(d,ball_x-64,860,1.6)
        self.type.text(image,'A movable wooden ball',540,1230,38,nature.PAPER,anchor='mm')
        self.type.text(image,'No food inside the ball',540,1300,28,nature.MUTED,anchor='mm')
    elif kind == 'bee_path':
        d.rounded_rectangle((140,735,940,1320),radius=35,outline='#80afae',width=6)
        d.rounded_rectangle((190,790,890,945),radius=25,fill='#153e45')
        self.type.text(image,'NEST',540,863,44,nature.PAPER,anchor='mm')
        _arrow(d,540,960,540,1140,nature.ICE,9)
        self.type.text(image,'CLEAR ROUTE TO FOOD',540,1190,33,nature.MINT,anchor='mm')
        for side in (-1,1):
            for i in range(3):
                x=540+side*(180+30*(i%2)); y=1003+72*i
                d.ellipse((x-33,y-33,x+33,y+33),fill='#d2a36f')
        self.type.text(image,'Balls off the main route',540,1390,29,nature.MUTED,anchor='mm')
    elif kind == 'bee_choice':
        for x,colour,txt in [(275,'#777eb5','Chamber A'),(810,'#edc65e','Chamber B')]:
            d.rounded_rectangle((x-215,805,x+205,1235),radius=28,
                                fill='#21383e',outline=colour,width=8)
            d.ellipse((x-90,910,x+90,1090),fill=colour)
            self.type.text(image,txt,x,1170,30,nature.PAPER,anchor='mm')
        _arrow(d,450,1300,660,1300,nature.MINT,9)
        self.type.text(image,'Previously linked to rolling',540,1390,33,
                       nature.ICE,anchor='mm')
    elif kind == 'bee_age':
        _bee(d,310,930,1.5);_bee(d,790,930,1.5)
        self.type.text(image,'Younger',310,1130,49,nature.MINT,anchor='mm')
        self.type.text(image,'Older',790,1130,49,nature.ICE,anchor='mm')
        self.type.text(image,'More frequent rolling\namong younger bees',540,1275,36,
                       nature.PAPER,anchor='mm')
    elif kind == 'bee_scope':
        _bee(d,540,915,1.5)
        self.type.block(image,'Play-like behaviour\nin a lab study',540,1110,55,
                        nature.PAPER,width=900,face='display',anchor='mt',max_lines=3)
        self.type.text(image,'Not a direct measure of bee feelings',540,1380,32,
                       nature.AMBER,anchor='mm')
    return image

Visuals.__init__ = _subject_init
Visuals.diagram = _subject_diagram
