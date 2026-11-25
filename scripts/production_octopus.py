"""Source-specific original Octopus chemical-trail illustrations.

A two-dimensional conceptual illustration of chemical-trail assays, NOT the actual
study recordings, apparatus dimensions, individual octopuss or measured paths.
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
FAMILY = 'octopus-plume-2025'
DOI = '10.1371/journal.pone.0330262'
SCENES = frozenset({'oct_plume','oct_stations','oct_upstream','oct_single','oct_count','oct_search','oct_arm','oct_suckers','oct_scope'})
WATER = '#317a9d'
SAND = '#c9a870'
FRAME = '#a6c5c4'
FILL = '#203d44'
GOLD = '#edba73'


def validate_motion_spec(episode):
    if (episode.get('id') != 'TT-012' or episode.get('doi') != DOI or
            episode.get('production', {}).get('scene_family') != FAMILY):
        raise ValueError('Octopus drawings are bound to the focal 2025 plume experiment')
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
        raise ValueError('Octopus story requires evidence-specific chemical-trail scenes')
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
            motion.Visuals.__init__.__code__, namespace, 'init_octopus_visuals',
            motion.Visuals.__init__.__defaults__, motion.Visuals.__init__.__closure__)
        init(self, episode, output, preview, timeline=timeline,
             artifact_root=artifact_root)

    def gradient_photo(self, key, t=0, focus=None):
        """Contain the whole octopus photo instead of an extreme vertical crop."""
        if key != 'octopus_reference':
            return super().gradient_photo(key, t, focus)
        image = self.background.copy()
        photo = self.photos.get(key)
        if photo is None:
            raise ValueError('Missing the SHA-pinned recognizable octopus photo')
        d = ImageDraw.Draw(image)
        d.rounded_rectangle((42, 596, 1038, 1414), radius=35,
                            fill=FILL, outline=FRAME, width=4)
        sized = ImageOps.contain(photo, (946, 750), Image.Resampling.LANCZOS)
        # Very slight editorial drift; no simulated octopus movement.
        phase = motion.ease(max(0.0, min(1.0, t / 7.0)))
        dx, dy = int(8 * (phase - .5)), int(7 * (.5 - phase))
        x = (nature.W - sized.width) // 2 + dx
        y = 620 + (738 - sized.height) // 2 + dy
        image.paste(sized, (x, y))
        self.type.text(image, 'SPECIES REFERENCE PHOTO · NOT A RECORDED TRIAL',
                       540, 1394, 28, nature.MUTED, anchor='mm')
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
    def _animal(d,x,y,s=1,lead=0):
        # Original schematic octopus: eight arms, a mantle and eyes.
        for j in range(8):
            a=math.tau*j/8
            reach=(122+lead if j==0 else 116)
            pts=[(x+math.cos(a)*24*s,y+math.sin(a)*24*s),
                 (x+math.cos(a+.27)*70*s,y+math.sin(a+.27)*70*s),
                 (x+math.cos(a)*reach*s,y+math.sin(a)*reach*s)]
            d.line(pts,fill='#cb815f',width=max(4,int(23*s)),joint='curve')
        d.ellipse((x-48*s,y-67*s,x+28*s,y+43*s),fill='#bf7355',outline='#f0b78b',width=max(2,int(4*s)))
        d.ellipse((x+10*s,y-31*s,x+26*s,y-15*s),fill='#192f33')
        d.ellipse((x+10*s,y+11*s,x+26*s,y+27*s),fill='#192f33')

    @staticmethod
    def _arrow(d,x1,y1,x2,y2,color,width=8):
        d.line((x1,y1,x2,y2),fill=color,width=width)
        a=math.atan2(y2-y1,x2-x1)
        d.polygon([(x2,y2),(x2-27*math.cos(a-.55),y2-27*math.sin(a-.55)),(x2-27*math.cos(a+.55),y2-27*math.sin(a+.55))],fill=color)

    def _tank(self,im,d,t,stations=1):
        d.rounded_rectangle((72,755,1008,1260),radius=30,fill='#123b47',outline='#8bb8b7',width=5)
        self._arrow(d,775,805,300,805,'#80c9df',7)
        self.type.text(im,'WATER FLOW',540,720,32,nature.ICE,anchor='mm')
        for y in ([935,1000,1065] if stations==3 else [1000]):
            bait=(y==1000)
            d.ellipse((860,y-27,914,y+27),fill='#edba73' if bait else '#43636b',outline='#d6e3df',width=4)
        # Discrete illustrative odor patches move downstream, away from bait.
        for j in range(16):
            f=(j/16+t*.14)%1
            x=857-700*f
            y=1000+math.sin(j*2.3+f*3)*(30+85*f)
            rad=6+10*f
            d.ellipse((x-rad,y-rad,x+rad,y+rad),fill='#83bbaa')
        self.type.text(im,'FOOD',890,1125,30,nature.PAPER,anchor='mm')
        if stations==3:
            self.type.text(im,'EMPTY STATIONS',540,1213,28,nature.MUTED,anchor='mm')
        else:
            self.type.text(im,'ILLUSTRATIVE CUE PATCHES',500,1205,27,nature.MUTED,anchor='mm')

    def diagram(self,kind,t,p,shot=None):
        if kind not in SCENES:
            return super().diagram(kind,t,p,shot)
        im=self.background.copy()
        d=ImageDraw.Draw(im)
        if kind in ('oct_plume','oct_stations','oct_upstream','oct_single','oct_search'):
            self._tank(im,d,t,3 if kind in ('oct_stations','oct_upstream') else 1)
            if kind in ('oct_upstream','oct_search'):
                f=motion.ease(max(0,min(1,p)))
                x=255+335*f
                y=1000+(48*math.sin(f*math.tau*2) if kind=='oct_search' else 0)
                self._animal(d,x,y,.67,15*math.sin(f*math.pi))
                self._arrow(d,300,1170,640,1170,GOLD,7)
                self.type.text(im,'UPSTREAM',470,1138,30,nature.PAPER,anchor='mm')
            elif kind!='oct_plume':
                self._animal(d,235,1000,.78)
            self._note(im,'CONCEPTUAL DIAGRAM · NO MEASURED PATH')
        elif kind=='oct_count':
            self.type.text(im,'41 SUCCESSFUL APPROACHES',540,780,43,nature.ICE,anchor='mm')
            for x,num,label,col in [(300,'31','INSIDE','#83bbaa'),(780,'10','OUTSIDE','#edba73')]:
                d.rounded_rectangle((x-200,875,x+200,1155),radius=26,fill=FILL,outline=col,width=5)
                self.type.text(im,num,x,960,104,nature.PAPER,anchor='mm')
                self.type.text(im,label,x,1085,39,nature.ICE,anchor='mm')
            self._note(im,'ESTIMATED PLUME · REPEATED EVENTS, NOT ANIMALS')
        elif kind=='oct_arm':
            self._animal(d,480,1000,2.15,45*motion.ease(max(0,min(1,p))))
            self._arrow(d,775,1020,925,1020,GOLD,7)
            self._note(im,'ILLUSTRATION OF ARM-ALIGNED MOTION')
        elif kind=='oct_suckers':
            d.line([(170,1090),(380,950),(630,920),(920,970)],fill='#cb815f',width=112,joint='curve')
            for j in range(8):
                x=225+j*90
                y=1060-115*math.sin(j*math.pi/9)
                d.ellipse((x-19,y-19,x+19,y+19),fill='#f1bda0',outline='#663f37',width=3)
            self.type.text(im,'POSSIBLE SENSORY ROLE',540,805,41,nature.ICE,anchor='mm')
            self._note(im,'NOT A TEST ISOLATING THE SUCKERS')
        elif kind=='oct_scope':
            self.type.block(im,'CHEMICAL TRAILS GUIDE SEARCH',540,850,50,nature.ICE,width=880,anchor='mt',max_lines=2)
            self.type.block(im,'PRECISE SENSORY PATHWAY UNKNOWN',540,1090,46,nature.PAPER,width=900,anchor='mt',max_lines=2)
        return im

def render(episode, voice, output, *, media_dir=None, qa_dir=None):
    validate_motion_spec(episode)
    namespace = dict(motion.render.__globals__)
    namespace.update(Visuals=Visuals, validate_motion_spec=validate_motion_spec)
    pipeline = types.FunctionType(
        motion.render.__code__, namespace, 'render_octopus_motion',
        motion.render.__defaults__, motion.render.__closure__)
    result = pipeline(episode, voice, output, media_dir=media_dir, qa_dir=qa_dir)
    result['motion_features']['transitions'] = ('Whole-art 0.18-second fade out before each boundary and 0.18-second fade in after it; no overlapping or sliced claims; captions and logo remain single')
    result['scene_family'] = FAMILY
    result['scene_doi'] = DOI
    return result
