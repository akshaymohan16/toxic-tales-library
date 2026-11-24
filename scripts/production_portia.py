"""Source-specific original Portia sleep behavior illustrations.

A two-dimensional conceptual illustration of sleep assays, NOT the actual
study recordings, apparatus dimensions, individual spiders or measured paths.
The frozen prior renderers and all previously approved release bytes are unchanged.
"""
import copy
import math
import types
from PIL import Image, ImageDraw, ImageOps
import production_motion as motion
import production_nature as nature
from motion_spec import motion_spec_sha256, validate_motion_spec as validate_base_spec

Voice = motion.Voice
VERSION = motion.VERSION
DECLARED_RENDERER = motion.DECLARED_RENDERER
FAMILY = 'portia-sleep-2026'
DOI = '10.1073/pnas.2618030123'
SCENES = frozenset({'portia_rest','portia_platform','portia_twitch','portia_retina','portia_tone','portia_latency','portia_count','portia_flies','portia_pair','portia_rebound','portia_scope'})
WATER = '#317a9d'
SAND = '#c9a870'
FRAME = '#a6c5c4'
FILL = '#203d44'
GOLD = '#edba73'


def validate_motion_spec(episode):
    if (episode.get('id') != 'TT-011' or episode.get('doi') != DOI or
            episode.get('production', {}).get('scene_family') != FAMILY):
        raise ValueError('Portia drawings are bound to the focal 2026 sleep experiment')
    normalized = copy.deepcopy(episode)
    matched = 0
    for segment in normalized['production']['segments']:
        for shot in segment['shots']:
            if shot['kind'] in SCENES:
                if shot.get('motion'):
                    raise ValueError('Schematic motion must not pretend measured time series')
                shot['kind'] = 'nature'
                matched += 1
    if matched < 8:
        raise ValueError('Portia story requires evidence-specific sleep scenes')
    receipt = validate_base_spec(normalized)
    receipt['spec_sha256'] = motion_spec_sha256(episode)
    receipt['scene_family'] = FAMILY
    receipt['scene_doi'] = DOI
    receipt['animation_timing_represents_measurement'] = False
    return receipt


class Visuals(motion.Visuals):
    def __init__(self, episode, output, preview=False, *, timeline=None, artifact_root=None):
        namespace = dict(motion.Visuals.__init__.__globals__)
        namespace['validate_motion_spec'] = validate_motion_spec
        init = types.FunctionType(
            motion.Visuals.__init__.__code__, namespace, 'init_portia_visuals',
            motion.Visuals.__init__.__defaults__, motion.Visuals.__init__.__closure__)
        init(self, episode, output, preview, timeline=timeline,
             artifact_root=artifact_root)

    def gradient_photo(self, key, t=0, focus=None):
        """Contain the whole spider photo instead of an extreme vertical crop."""
        if key != 'portia_reference':
            return super().gradient_photo(key, t, focus)
        image = self.background.copy()
        photo = self.photos.get(key)
        if photo is None:
            raise ValueError('Missing the SHA-pinned recognizable spider photo')
        d = ImageDraw.Draw(image)
        d.rounded_rectangle((42, 596, 1038, 1414), radius=35,
                            fill=FILL, outline=FRAME, width=4)
        sized = ImageOps.contain(photo, (946, 750), Image.Resampling.LANCZOS)
        # Very slight editorial drift; no simulated spider movement.
        phase = motion.ease(max(0.0, min(1.0, t / 7.0)))
        dx, dy = int(8 * (phase - .5)), int(7 * (.5 - phase))
        x = (nature.W - sized.width) // 2 + dx
        y = 620 + (738 - sized.height) // 2 + dy
        image.paste(sized, (x, y))
        self.type.text(image, 'SPECIES REFERENCE PHOTO · NOT A RECORDED TRIAL',
                       540, 1420, 28, nature.MUTED, anchor='mm')
        return image

    def transition(self, image, shot, t):
        """Fade the complete current artwork, never mix different claims.
        
        Titles/captions are added after this step. Fade out before a real
        boundary and in after it so no new title overlays previous data.
        """
        half = motion.TRANSITION_SECONDS / 2
        start, end = shot['start'], shot['end']
        before = any(abs(item['end'] - start) < 1e-5 and item['start'] < start
                     for item in self.timeline)
        after = any(abs(item['start'] - end) < 1e-5 and item['end'] > end
                    for item in self.timeline)
        alpha = 1.0
        if before:
            alpha = min(alpha, motion.ease(max(0.0, min(1.0, (t - start) / half))))
        if after:
            alpha = min(alpha, motion.ease(max(0.0, min(1.0, (end - t) / half))))
        return image if alpha >= 1.0 else Image.blend(self.background, image, alpha)

    def _note(self, im, words):
        self.type.block(im, words, 540, 1320, 28, nature.MUTED,
                        width=880, anchor='mt', max_lines=2)

    @staticmethod
    def _spider(d, x, y, scale=1, twitch=0):
        # Stylized two body regions and eight legs; not a measured pose.
        def pt(a,b):
            return (x+a*scale, y+b*scale)
        def ellipse(a,b,c,e,fill):
            d.ellipse((*pt(a,b),*pt(c,e)),fill=fill,outline='#cfba92',width=max(2,int(4*scale)))
        for side in (-1,1):
            for j in range(4):
                dy=-50+j*30
                lift=twitch if j in (0,3) else 0
                d.line([pt(side*33,dy),pt(side*(100+j*5),dy-45),
                        pt(side*(151+j*9),dy+35+lift)],fill='#d2aa73',
                        width=max(3,int(10*scale)),joint='curve')
        ellipse(-43,-92,43,7,'#795b42')
        ellipse(-64,0,64,120,'#584735')
        ellipse(-26,-80,-3,-57,'#203133')
        ellipse(3,-80,26,-57,'#203133')

    def diagram(self, kind, t, p, shot=None):
        if kind not in SCENES:
            return super().diagram(kind,t,p,shot)
        im=self.background.copy()
        d=ImageDraw.Draw(im)
        if kind in ('portia_rest','portia_platform','portia_twitch'):
            for y in (800,815,830):
                d.line((150,y,930,y),fill='#b9c6c1',width=3)
            twitch=14*math.sin(t*8) if kind=='portia_twitch' else 0
            self._spider(d,540,1025,1.45,twitch)
            self.type.text(im,'SILK PLATFORM',540,746,36,nature.ICE,anchor='mm')
            self._note(im,'SCHEMATIC REST POSTURE · MOVEMENT NOT RECORDED')
        elif kind=='portia_retina':
            for x in (325,755):
                d.ellipse((x-170,780,x+170,1130),fill='#2b4a50',outline='#a5c6c4',width=7)
                offset=int(28*math.sin(t*3))
                d.line((x,825,x+offset,1045),fill='#edba73',width=38)
                d.ellipse((x+offset-31,1014,x+offset+31,1076),fill='#ecd5b0')
            self.type.text(im,'INTERNAL RETINAL TUBES',540,704,38,nature.ICE,anchor='mm')
            self._note(im,'CONCEPTUAL MOTION · NOT A MEASURED EYE TRACE')
        elif kind=='portia_tone':
            self._spider(d,730,1010,.9)
            d.rounded_rectangle((155,875,320,1135),radius=20,fill='#547175',outline='#a6c5c4',width=5)
            for j in range(3):
                q=int(25*((t*.8+j*.2)%1))
                d.arc((230-q-j*26,805-q-j*26,460+q+j*26,1200+q+j*26),-60,60,fill='#e6c889',width=5)
            self.type.text(im,'SOUND STIMULUS',540,724,42,nature.ICE,anchor='mm')
            self._note(im,'400 HZ · UP TO 10 SECONDS · SCHEMATIC')
        elif kind=='portia_latency':
            for x,v,label in [(292,'1.69 s','AWAKE'),(788,'4.27 s','REM-LIKE')]:
                self.type.text(im,v,x,947,82,nature.PAPER,anchor='mm')
                self.type.text(im,label,x,1078,37,nature.ICE,anchor='mm')
            self._note(im,'ESTIMATED MEAN LATENCY AMONG RESPONDERS ONLY')
        elif kind=='portia_count':
            self.type.text(im,'4 OF 10',540,793,82,nature.PAPER,anchor='mm')
            for i in range(10):
                x=300+(i%5)*120
                y=960+(i//5)*115
                d.ellipse((x-37,y-37,x+37,y+37),fill='#edba73' if i<4 else '#426e66',outline='#d0dbce',width=3)
            self._note(im,'GOLD: NO RESPONSE WITHIN 10 S · REM-LIKE GROUP')
        elif kind=='portia_flies':
            self._spider(d,540,1010,.85)
            for j in range(6):
                a=t*.6+j*math.tau/6
                x=540+300*math.cos(a)
                y=1000+200*math.sin(a)
                d.ellipse((x-9,y-16,x+9,y+16),fill='#d5ae7e')
                d.ellipse((x-26,y-10,x,y+10),outline='#d5e2d9',width=3)
                d.ellipse((x,y-10,x+26,y+10),outline='#d5e2d9',width=3)
            self._note(im,'ILLUSTRATIVE FLIES · ICON COUNT IS NOT THE DOSE')
        elif kind=='portia_pair':
            for i in range(13):
                x=180+(i%7)*120
                y=925+(i//7)*125
                d.ellipse((x-37,y-37,x+37,y+37),fill='#426e66',outline='#c9d9d1',width=3)
            self.type.text(im,'13 PAIRED RECORDINGS',540,745,43,nature.ICE,anchor='mm')
            self._note(im,'SAME SPIDERS BEFORE AND AFTER DISTURBANCE')
        elif kind=='portia_rebound':
            for x,v,label in [(292,'9.4','BEFORE'),(788,'16.9','AFTER')]:
                self.type.text(im,v,x,925,108,nature.PAPER,anchor='mm')
                self.type.text(im,label,x,1060,37,nature.ICE,anchor='mm')
            self._note(im,'MEAN TOTAL REM-LIKE MINUTES · 13 PAIRED SPIDERS')
        elif kind=='portia_scope':
            self.type.block(im,'POSTURE + AROUSAL + REBOUND',540,820,53,nature.ICE,width=900,anchor='mt',max_lines=2)
            self.type.block(im,'NO DIRECT NEURAL RECORDING',540,1080,48,nature.PAPER,width=900,anchor='mt',max_lines=2)
            self._note(im,'BEHAVIORAL EVIDENCE IS NOT PROOF OF DREAMING')
        return im


def render(episode, voice, output, *, media_dir=None, qa_dir=None):
    validate_motion_spec(episode)
    namespace = dict(motion.render.__globals__)
    namespace.update(Visuals=Visuals, validate_motion_spec=validate_motion_spec)
    pipeline = types.FunctionType(
        motion.render.__code__, namespace, 'render_portia_motion',
        motion.render.__defaults__, motion.render.__closure__)
    result = pipeline(episode, voice, output, media_dir=media_dir, qa_dir=qa_dir)
    result['motion_features']['transitions'] = ('Whole-art 0.18-second fade out before each boundary and 0.18-second fade in after it; no overlapping or sliced claims; captions and logo remain single')
    result['scene_family'] = FAMILY
    result['scene_doi'] = DOI
    return result
