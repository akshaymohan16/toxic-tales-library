"""Original source-specific Cataglyphis rescue illustrations for TT-009.

Schematic animation, not reconstructions of the observed rescue footage.
This is an additive renderer; frozen renderers and existing release bytes are untouched.
"""
import copy
import math
import types
from PIL import Image, ImageDraw, ImageOps
import production_motion as motion
import production_nature as nature
from motion_spec import motion_spec_sha256
from motion_spec import validate_motion_spec as validate_base_spec

Voice = motion.Voice
VERSION = motion.VERSION
DECLARED_RENDERER = motion.DECLARED_RENDERER
FAMILY = 'cataglyphis-rescue-2009'
DOI = '10.1371/journal.pone.0006573'
SCENES = frozenset({'ant_trap', 'ant_dig', 'ant_thread', 'ant_comparison',
                    'ant_findings', 'ant_workers', 'ant_limit', 'ant_close'})


def validate_motion_spec(episode):
    if episode.get('doi') != DOI or episode.get('production', {}).get('scene_family') != FAMILY:
        raise ValueError('Ant rescue renderer is restricted to the original 2009 study')
    normalized = copy.deepcopy(episode)
    matched = 0
    for segment in normalized['production']['segments']:
        for shot in segment['shots']:
            if shot['kind'] in SCENES:
                if shot.get('motion'):
                    raise ValueError('Ant diagrams cannot encode fabricated quantitative motion')
                shot['kind'] = 'nature'
                matched += 1
    if matched < 6:
        raise ValueError('Ant story needs multiple distinct evidence-specific scenes')
    receipt = validate_base_spec(normalized)
    receipt['spec_sha256'] = motion_spec_sha256(episode)
    receipt['scene_family'] = FAMILY
    receipt['scene_doi'] = DOI
    return receipt


class Visuals(motion.Visuals):
    def __init__(self, episode, output, preview=False, *, timeline=None, artifact_root=None):
        namespace = dict(motion.Visuals.__init__.__globals__)
        namespace['validate_motion_spec'] = validate_motion_spec
        initialize = types.FunctionType(
            motion.Visuals.__init__.__code__, namespace, 'init_ant_visuals',
            motion.Visuals.__init__.__defaults__, motion.Visuals.__init__.__closure__)
        initialize(self, episode, output, preview, timeline=timeline,
                   artifact_root=artifact_root)

    def gradient_photo(self, key, t=0, focus=None):
        """Source-specific intact-ant composition; do not crop a landscape specimen
        into an unrecognisable portrait fragment. Dorsal specimen is a licensed
        related subspecies, NOT the observed laboratory rescuer.
        """
        if key != 'cursor_reference':
            return super().gradient_photo(key, t, focus)
        source = self.photos.get(key)
        if source is None:
            raise ValueError('Missing pinned full-ant reference specimen')
        image = self.background.copy()
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((51, 630, 1029, 1438), radius=32,
                               fill='#15292b', outline='#4c6b62', width=3)
        ant = ImageOps.contain(source, (940, 745), Image.Resampling.LANCZOS)
        phase = motion.ease(max(0.0, min(1.0, t / 8.0)))
        # Less than 10-pixel editorial drift; no simulated ant movement.
        dx = int(8 * (phase - .5))
        dy = int(8 * (.5 - phase))
        x = (nature.W - ant.width) // 2 + dx
        y = 656 + (745 - ant.height) // 2 + dy
        image.paste(ant, (x, y))
        # Readable, scene-specific provenance instead of a recurring footer.
        self.type.text(image, 'RELATED SUBSPECIES · REFERENCE SPECIMEN',
                       540, 1452, 27, nature.ICE, anchor='mt')
        return image

    @staticmethod
    def _ant(draw, x, y, scale=1.0, facing=1, phase=0, pale=False):
        """Three-segment diagram with articulated legs, no simulated measured track."""
        color = '#809795' if pale else '#c59b67'
        deep = '#334e49' if pale else '#785038'
        radii = ((-67, -8, 49, 35), (3, -7, 31, 27), (65, -11, 31, 28))
        for dx, dy, rx, ry in radii:
            cx, cy = x + facing * dx * scale, y + dy * scale
            draw.ellipse((cx-rx*scale,cy-ry*scale,cx+rx*scale,cy+ry*scale),
                         fill=color,outline=deep,width=max(2,int(scale*4)))
        for side in (-1, 1):
            for j in range(3):
                ax=x+facing*(j-1)*38*scale
                ay=y+side*8*scale
                step=9*math.sin(phase*2+j*1.6+side)
                knee=(ax+facing*(j-1)*26*scale, ay+side*49*scale)
                toe=(knee[0]+step*scale, knee[1]+side*44*scale)
                draw.line([(ax,ay),knee,toe],fill='#bea17c',width=max(2,int(scale*5)),joint='curve')
        head=x+facing*74*scale
        draw.ellipse((head-facing*3*scale,y-24*scale,head+facing*3*scale,y-18*scale), fill='#172927')
        draw.line([(head,y-30*scale),(head+facing*32*scale,y-61*scale),
                   (head+facing*43*scale,y-75*scale)],
                  fill='#d6b98e',width=max(2,int(scale*3)))
        draw.line([(head,y-23*scale),(head+facing*25*scale,y-57*scale),
                   (head+facing*37*scale,y-60*scale)],
                  fill='#d6b98e',width=max(2,int(scale*3)))

    def _sand(self, image, level=1120, t=0):
        d=ImageDraw.Draw(image)
        d.rounded_rectangle((60,level,1020,1430),radius=36,
                            fill='#283b39',outline='#668477',width=3)
        d.line([(90,level+int(3*math.sin(i/80+t*.3))) for i in range(90,1000,8)],
               fill='#d2b984',width=6)
        for i in range(34):
            x=115+(i*113)%840
            y=level+48+(i*57)%232
            r=2+i%3
            d.ellipse((x-r,y-r,x+r,y+r),fill=('#ac9270' if i%3 else '#7f7960'))
        return d

    def _rig(self, draw, exposed=0):
        """Filter disc, nylon loop, and fixed restraint are explicitly diagrammatic."""
        disc_y=1183+int((1-exposed)*78)
        draw.ellipse((390,disc_y,690,disc_y+63),
                     fill='#b9beb5',outline='#ece8d9',width=4)
        draw.line([(540,disc_y+3),(527,1070),(555,997)],
                  fill='#d8e5df',width=8)
        draw.arc((512,979,571,1037),10,325,fill='#edf4ee',width=8)

    def _note(self,image,text):
        self.type.text(image,text,540,1436,25,nature.MUTED,anchor='mm')

    def diagram(self,kind,t,p,shot=None):
        if kind not in SCENES:
            return super().diagram(kind,t,p,shot)
        if self.ep.get('doi')!=DOI:
            raise ValueError('Ant scene outside reviewed source identity')
        im=self.background.copy()
        d=self._sand(im,t=t)
        if kind in {'ant_trap','ant_dig','ant_thread','ant_close'}:
            exposure=min(1,max(0,t*.22)) if kind=='ant_dig' else .75 if kind=='ant_thread' else .34
            self._rig(d,exposed=exposure)
            self._ant(d,540,1004,1.18,1,phase=t,pale=True)
            if kind=='ant_trap':
                self._ant(d,250,965,.84,1,phase=t)
                self._note(im,'NYLON SNARE - LABORATORY DIAGRAM')
            elif kind=='ant_dig':
                self._ant(d,282,1047,.88,1,phase=t)
                for j in range(11):
                    x=350+int(180*math.sin(.4*j+t*.8))
                    y=1134-int((j*47+t*23)%105)
                    d.ellipse((x-6,y-6,x+6,y+6),fill='#d3ac76')
                self._note(im,'DIGGING AND MOVING SAND - SCHEMATIC')
            elif kind=='ant_thread':
                self._ant(d,316,1004,.91,1,phase=t)
                delta=7*math.sin(t*2.7)
                d.line([(427,1020),(496+delta,995)],fill='#ffd19d',width=8)
                d.ellipse((481+delta,983,500+delta,1008),fill='#ffdd93')
                self.type.text(im,'BITING THE THREAD',540,740,39,nature.ICE,anchor='mm')
                self._note(im,'PRECISE SNARE BITING - NOT A CUTTING CLAIM')
            else:
                self._ant(d,287,1017,.89,1,phase=t)
                self._note(im,'PRECISION TOWARD A RESTRAINT - LAB TEST')
        elif kind=='ant_comparison':
            d.rounded_rectangle((78,742,507,1260),radius=24,fill='#243b37',outline='#a5c5ac',width=3)
            d.rounded_rectangle((572,742,1002,1260),radius=24,fill='#203138',outline='#70808a',width=3)
            for x,y,active in [(294,938,True),(789,938,False)]:
                self._ant(d,x,y,1.0,1,phase=t if active else 0,pale=not active)
                d.line((x-25,1012,x+10,1092),fill='#e6d5b3',width=6)
            self.type.text(im,'ACTIVE NESTMATE',294,1191,27,nature.ICE,weight=700,anchor='mm')
            self.type.text(im,'OTHER CONTROLS',785,1191,27,nature.MUTED,weight=700,anchor='mm')
            self._note(im,'SIX CONDITIONS; THREE SOURCE COLONIES')
        elif kind=='ant_findings':
            d.rounded_rectangle((80,720,1000,1210),radius=33,outline='#71958a',width=3,fill='#203c36')
            self.type.text(im,'9 of 9',540,833,98,nature.PAPER,weight=750,anchor='mm')
            self.type.text(im,'active nestmate group tests showed rescue',540,925,31,nature.ICE,anchor='mm')
            d.line((142,996,938,996),fill='#64847d',width=3)
            self.type.text(im,'None in 45 other group tests',540,1061,36,nature.MUTED,anchor='mm')
            self._note(im,'OBSERVED COUNTS - NINE GROUP TESTS PER CONDITION')
        elif kind=='ant_workers':
            for j in range(5):
                x=137+j*200
                bright=j<(1+int(abs(math.sin(t*.24))*2.5))
                self._ant(d,x,905,.62,1,phase=t if bright else 0,pale=not bright)
            self.type.text(im,'One to three workers',540,1152,53,nature.PAPER,anchor='mm')
            self.type.text(im,'of each five-worker group performed rescue',540,1219,27,nature.MUTED,anchor='mm')
            self._note(im,'GROUPS WERE THE STATISTICAL REPLICATES')
        elif kind=='ant_limit':
            d.rounded_rectangle((91,685,989,1294),radius=30,outline='#6d8b7b',width=3,fill='#233731')
            for j in range(3):
                self._ant(d,286+j*255,847,.77,1,phase=t*.3,pale=j==2)
            self.type.text(im,'WHAT WAS NOT TESTED',540,1038,43,nature.ICE,weight=680,anchor='mm')
            self.type.block(im,'Empathy, wild rescue rates,\nand the exact signals used',540,1112,36,
                            nature.PAPER,width=860,anchor='mt',max_lines=3)
            self._note(im,'CONTROLLED EXPERIMENT - NOT A WILD OBSERVATION')
        return im


def render(episode,voice,output,*,media_dir=None,qa_dir=None):
    validate_motion_spec(episode)
    namespace=dict(motion.render.__globals__)
    namespace.update(Visuals=Visuals,validate_motion_spec=validate_motion_spec)
    pipeline=types.FunctionType(motion.render.__code__,namespace,'render_ant_motion',
                                motion.render.__defaults__,motion.render.__closure__)
    result=pipeline(episode,voice,output,media_dir=media_dir,qa_dir=qa_dir)
    result['scene_family']=FAMILY
    result['scene_doi']=DOI
    return result
