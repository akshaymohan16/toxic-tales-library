"""Source-specific original 2014 crow water-displacement illustrations.

A two-dimensional conceptual illustration of physical choices, NOT the actual
study recordings, apparatus dimensions, individual birds or measured paths.
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
FAMILY = 'corvus-water-2014'
DOI = '10.1371/journal.pone.0092895'
SCENES = frozenset({
    'crow_stone', 'crow_compare', 'crow_sink', 'crow_solid', 'crow_high',
    'crow_narrow', 'crow_u', 'crow_result', 'crow_recap', 'crow_limits'
})
WATER = '#317a9d'
SAND = '#c9a870'
FRAME = '#a6c5c4'
FILL = '#203d44'
GOLD = '#edba73'


def validate_motion_spec(episode):
    if (episode.get('id') != 'TT-010' or episode.get('doi') != DOI or
            episode.get('production', {}).get('scene_family') != FAMILY):
        raise ValueError('Crow drawings are bound to the focal 2014 crow experiment')
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
        raise ValueError('Crow story requires evidence-specific original physics scenes')
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
            motion.Visuals.__init__.__code__, namespace, 'init_crow_visuals',
            motion.Visuals.__init__.__defaults__, motion.Visuals.__init__.__closure__)
        init(self, episode, output, preview, timeline=timeline,
             artifact_root=artifact_root)

    def gradient_photo(self, key, t=0, focus=None):
        """Contain the whole wild-bird photo instead of an extreme vertical crop."""
        if key != 'crow_reference':
            return super().gradient_photo(key, t, focus)
        image = self.background.copy()
        photo = self.photos.get(key)
        if photo is None:
            raise ValueError('Missing the SHA-pinned recognizable crow photo')
        d = ImageDraw.Draw(image)
        d.rounded_rectangle((42, 596, 1038, 1414), radius=35,
                            fill=FILL, outline=FRAME, width=4)
        sized = ImageOps.contain(photo, (946, 750), Image.Resampling.LANCZOS)
        # Very slight editorial drift; no simulated crow movement.
        phase = motion.ease(max(0.0, min(1.0, t / 7.0)))
        dx, dy = int(8 * (phase - .5)), int(7 * (.5 - phase))
        x = (nature.W - sized.width) // 2 + dx
        y = 620 + (738 - sized.height) // 2 + dy
        image.paste(sized, (x, y))
        self.type.text(image, 'WILD REFERENCE PHOTO · NOT A RECORDED TRIAL',
                       540, 1450, 28, nature.MUTED, anchor='mm')
        return image

    @staticmethod
    def _tube(image, cx, *, top=743, bottom=1260, width=195, level=.45,
              water=True, reward=True, stone=False, t=0):
        d = ImageDraw.Draw(image)
        left, right = int(cx - width / 2), int(cx + width / 2)
        d.rounded_rectangle((left, top, right, bottom), radius=23,
                            fill='#142c34', outline=FRAME, width=7)
        y = int(bottom - (bottom - top - 18) * level)
        d.rectangle((left + 9, y, right - 9, bottom - 9),
                    fill=WATER if water else SAND)
        d.line((left + 11, y, right - 11, y), fill='#d3e6df', width=5)
        if water and reward:
            # A small fixed cork-and-food icon, not a measured data point.
            d.ellipse((cx - 28, y - 18, cx + 28, y - 1),
                      fill='#e0c59d', outline='#936e4a', width=3)
            d.rectangle((cx - 16, y - 31, cx + 16, y - 17), fill=GOLD)
        if stone:
            progress = motion.ease(max(0.0, min(1.0, t / 3.0)))
            # A schematic action: the arbitrary timing is not experiment data.
            stone_y = top - 80 + int((y + 70 - (top - 80)) * progress)
            if water:
                # The schematic liquid rise is qualitative.
                raise_by = int(30 * progress)
                if raise_by:
                    d.rectangle((left + 9, y - raise_by, right - 9, y), fill=WATER)
                    d.line((left + 11, y - raise_by, right - 11, y - raise_by),
                           fill='#d3e6df', width=5)
            d.ellipse((cx - 19, stone_y - 17, cx + 19, stone_y + 17),
                      fill='#8d9395', outline='#d3d8d9', width=3)
        return y

    @staticmethod
    def _square(image, x, y, side, *, solid=True):
        d = ImageDraw.Draw(image)
        box = (x - side/2, y - side/2, x + side/2, y + side/2)
        d.rounded_rectangle(box, radius=12,
                            fill='#d1a77a' if solid else '#1d3940',
                            outline='#e9d2b3', width=7)
        if solid:
            d.line((x-side*.23, y-side*.24, x+side*.15, y+side*.22),
                   fill='#8e6947', width=5)

    def _note(self, image, text):
        self.type.block(image, text, 540, 1316, 28, nature.MUTED,
                        width=880, anchor='mt', max_lines=2)

    def diagram(self, kind, t, p, shot=None):
        if kind not in SCENES:
            return super().diagram(kind, t, p, shot)
        im = self.background.copy()
        d = ImageDraw.Draw(im)
        if kind == 'crow_stone':
            self._tube(im, 540, width=282, level=.45, stone=True, t=t)
            self.type.text(im, 'A STONE DISPLACES WATER', 540, 678, 38,
                           nature.ICE, anchor='mm')
            self._note(im, 'ILLUSTRATIVE WATER LEVEL · NOT A RECORDED DROP')
        elif kind == 'crow_compare':
            self._tube(im, 294, width=210, level=.5, water=True, stone=True, t=t)
            self._tube(im, 787, width=210, level=.5, water=False, reward=False,
                       stone=True, t=t)
            self.type.text(im, 'WATER', 294, 674, 47, nature.ICE, anchor='mm')
            self.type.text(im, 'SAND', 787, 674, 47, nature.ICE, anchor='mm')
            self._note(im, 'ONLY WATER CAN LIFT THE FLOATING REWARD')
        elif kind == 'crow_sink':
            self._tube(im, 295, width=232, level=.40, stone=True, t=t)
            self._tube(im, 786, width=232, level=.40)
            # A floating ball rests on the second water surface.
            level_y = int(1260 - (1260 - 743 - 18)*.4)
            d.ellipse((765, level_y-27, 807, level_y+15),
                      fill='#f0d8ad', outline='#e1ab70', width=3)
            self.type.text(im, 'SINKING', 295, 676, 37, nature.ICE, anchor='mm')
            self.type.text(im, 'FLOATING', 786, 676, 37, nature.ICE, anchor='mm')
            self._note(im, 'SINKING OBJECTS INCREASE EFFECTIVE DISPLACEMENT')
        elif kind == 'crow_solid':
            self._tube(im, 296, width=214, level=.44, reward=False)
            self._tube(im, 784, width=214, level=.44, reward=False)
            self._square(im, 296, 939, 80, solid=True)
            self._square(im, 784, 939, 80, solid=False)
            self.type.text(im, 'SOLID', 296, 677, 46, nature.ICE, anchor='mm')
            self.type.text(im, 'HOLLOW', 784, 677, 46, nature.ICE, anchor='mm')
            self._note(im, 'STUDY OBJECTS WERE SAME SIZE AND WEIGHT')
        elif kind == 'crow_high':
            self._tube(im, 295, width=224, level=.72, reward=True)
            self._tube(im, 785, width=224, level=.20, reward=True)
            self.type.text(im, 'HIGHER START', 295, 673, 39, nature.ICE,
                           anchor='mm')
            self.type.text(im, 'TOO LOW', 785, 673, 39, nature.ICE,
                           anchor='mm')
            self._note(im, 'THE USEFUL STARTING LEVEL WAS LEARNED OVER TRIALS')
        elif kind == 'crow_narrow':
            self._tube(im, 298, width=145, level=.43, reward=True)
            self._tube(im, 774, width=310, level=.43, reward=True)
            self.type.text(im, 'NARROW', 298, 672, 40, nature.ICE, anchor='mm')
            self.type.text(im, 'WIDE', 774, 672, 40, nature.ICE, anchor='mm')
            self._note(im, 'NO RELIABLE FIRST-DROP PREFERENCE FOR THE NARROW TUBE')
        elif kind == 'crow_u':
            self._tube(im, 247, width=183, top=800, bottom=1185, level=.35, reward=False)
            self._tube(im, 545, width=145, top=800, bottom=1185, level=.35, reward=True)
            self._tube(im, 837, width=183, top=800, bottom=1185, level=.35, reward=False)
            # Reveal the hidden causal link to the viewer as a schematic.
            d.line([(247,1202),(247,1221),(545,1221),(545,1202)],
                   fill=GOLD,width=12,joint='curve')
            d.line((120,1262,957,1262), fill='#718888', width=5)
            self.type.text(im, 'HIDDEN UNDER THE OPAQUE BASE', 540, 704,
                           30, nature.ICE, anchor='mm')
            self._note(im, 'THE CROW COULD NOT SEE THE CONNECTED TUBE')
        elif kind == 'crow_result':
            self.type.text(im, '48.9%', 540, 896, 136,
                           nature.PAPER, anchor='mm')
            self.type.block(im, 'DROPS INTO THE CONNECTED U-TUBE', 540, 1019, 40,
                            nature.ICE, width=900, anchor='mt', max_lines=2)
            self.type.text(im, 'NEAR CHANCE · FOUR BIRDS', 540, 1174, 31,
                           nature.MUTED, anchor='mm')
            self._note(im, 'THIS IS AN AGGREGATE; NO INDIVIDUAL PATH IS SHOWN')
        elif kind == 'crow_recap':
            labels=[('WATER','USEFUL'),('SINKING','USEFUL'),('SOLID','USEFUL'),
                    ('HIGH WATER','USEFUL'),('NARROW','NOT FAVOURED'),
                    ('HIDDEN LINK','NEAR CHANCE')]
            for i,(txt,status) in enumerate(labels):
                x=314 if i%2==0 else 772
                y=752+i//2*208
                d.rounded_rectangle((x-201,y-75,x+201,y+75),
                    radius=23,fill='#235d54' if status=='USEFUL' else '#293b42',
                    outline='#91b7a6' if status=='USEFUL' else '#8b9895',width=3)
                self.type.text(im, txt, x,y-18,31,nature.PAPER,anchor='mm')
                self.type.text(im,status,x,y+37,24,nature.MUTED,anchor='mm')
            self._note(im, 'THE CROWS WERE SELECTIVE — NOT INFALLIBLE')
        elif kind == 'crow_limits':
            self.type.text(im, '6 BEGAN · 4 FINISHED', 540, 771, 46,
                           nature.PAPER, anchor='mm')
            for i in range(6):
                x=216+i*130
                y=1033
                col='#8cc1a5' if i<4 else '#54666a'
                d.ellipse((x-43,y-43,x+43,y+43),
                          fill=col,outline='#e3efea',width=3)
            self.type.text(im,'TRAINING + FIXED TASK ORDER',540,1175,35,
                           nature.ICE,anchor='mm')
            self._note(im,'SMALL CONTROLLED STUDY, NOT WILD STONE DROPPING')
        return im


def render(episode, voice, output, *, media_dir=None, qa_dir=None):
    validate_motion_spec(episode)
    namespace = dict(motion.render.__globals__)
    namespace.update(Visuals=Visuals, validate_motion_spec=validate_motion_spec)
    pipeline = types.FunctionType(
        motion.render.__code__, namespace, 'render_crow_motion',
        motion.render.__defaults__, motion.render.__closure__)
    result = pipeline(episode, voice, output, media_dir=media_dir, qa_dir=qa_dir)
    result['scene_family'] = FAMILY
    result['scene_doi'] = DOI
    return result
