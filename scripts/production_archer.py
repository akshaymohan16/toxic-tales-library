"""Archerfish face-choice scenes layered on the frozen motion production stack.

These are explicitly labelled task illustrations, not reconstructed trial data.
The existing voice, caption, audio, geometry, branding and exact-export gates
run unchanged in isolated function namespaces; old renderer files stay frozen.
"""
import copy
import math
import types

from PIL import Image, ImageDraw

import production_motion as motion
import production_nature as nature
from motion_spec import motion_spec_sha256
from motion_spec import validate_motion_spec as validate_base_spec

Voice = motion.Voice
VERSION = motion.VERSION
DECLARED_RENDERER = motion.DECLARED_RENDERER
FAMILY = 'archerfish-face-2016'
DOI = '10.1038/srep27523'
SCENES = frozenset({'archer_hunt', 'archer_task', 'archer_transfer',
                    'archer_controls', 'archer_result', 'archer_scope'})


def validate_motion_spec(episode):
    """Extend only scene vocabulary; keep the original provenance gate intact."""
    plan = episode.get('production', {})
    if plan.get('scene_family') != FAMILY or episode.get('doi') != DOI:
        raise ValueError('Archerfish scenes require their exact source DOI and family')
    normalized = copy.deepcopy(episode)
    scene_count = 0
    for segment in normalized.get('production', {}).get('segments', []):
        for shot in segment.get('shots', []):
            if shot.get('kind') in SCENES:
                if shot.get('motion'):
                    raise ValueError('Archerfish task diagrams cannot carry numerical data')
                scene_count += 1
                # Only validation uses this neutral base vocabulary. Rendering
                # and fingerprints retain the exact actual source-specific kind.
                shot['kind'] = 'nature'
    if not scene_count:
        raise ValueError('Archerfish production requires source-specific moving scenes')
    receipt = validate_base_spec(normalized)
    receipt['spec_sha256'] = motion_spec_sha256(episode)
    receipt['scene_family'] = FAMILY
    receipt['scene_doi'] = DOI
    return receipt


class Visuals(motion.Visuals):
    def __init__(self, episode, output, preview=False, *, timeline=None, artifact_root=None):
        namespace = dict(motion.Visuals.__init__.__globals__)
        namespace['validate_motion_spec'] = validate_motion_spec
        initialize = types.FunctionType(motion.Visuals.__init__.__code__, namespace,
                                        'initialize_archer_visuals',
                                        motion.Visuals.__init__.__defaults__,
                                        motion.Visuals.__init__.__closure__)
        initialize(self, episode, output, preview, timeline=timeline, artifact_root=artifact_root)
        for asset in episode['production']['assets']:
            box = asset.get('source_crop_box')
            if box is None:
                continue
            image = self.photos.get(asset['id'])
            if (image is None or not isinstance(box, list) or len(box) != 4
                    or any(type(value) is not int for value in box)
                    or not 0 <= box[0] < box[2] <= image.width
                    or not 0 <= box[1] < box[3] <= image.height):
                raise ValueError('Source panel crop must be valid integer pixel bounds')
            # Preserve the original licensed download/hash; use only the
            # declared panel in the composition, with all changes in credits.
            self.photos[asset['id']] = image.crop(tuple(box))

    def _fish(self, image, cx, cy, scale=1., t=0., angle=20):
        """Species-inspired diagram with banding; no tracking data implied."""
        sprite = Image.new('RGBA', (420, 220))
        d = ImageDraw.Draw(sprite)
        tail = 9 * math.sin(t * 2.2)
        d.polygon([(94, 106), (27, 51 + tail), (39, 111), (27, 168 + tail)],
                  fill='#8aaf9d', outline=nature.ICE)
        d.polygon([(130, 72), (151, 32), (183, 59), (203, 28), (228, 57),
                   (251, 42), (279, 75)], fill='#687c6f', outline=nature.MUTED)
        d.ellipse((78, 62, 342, 160), fill='#ced2b8', outline='#e3ead7', width=3)
        d.polygon([(273, 65), (328, 75), (361, 103), (335, 139), (291, 155)],
                  fill='#dce0c8', outline='#dce0c8')
        for x in (113, 157, 201, 246, 290):
            d.polygon([(x - 7, 66), (x + 15, 71), (x - 2, 145), (x - 20, 144)],
                      fill='#284139')
        d.arc((111, 87, 283, 160), 5, 167, fill='#f5f1da', width=5)
        d.polygon([(207, 119), (166, 174 + 5 * math.sin(t * 2)), (239, 139)],
                  fill='#a8ba9d', outline='#deead1')
        d.ellipse((298, 83, 322, 107), fill='#dccd93', outline='#fcf4d7', width=2)
        d.ellipse((305, 87, 318, 100), fill='#061b1c')
        d.ellipse((309, 89, 313, 93), fill=nature.PAPER)
        d.line((343, 106, 361, 103), fill='#344c41', width=3)
        sprite = sprite.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        sprite = sprite.resize((round(sprite.width * scale), round(sprite.height * scale)),
                               Image.Resampling.LANCZOS)
        image.paste(sprite, (round(cx - sprite.width / 2), round(cy - sprite.height / 2)), sprite)
        theta = math.radians(angle)
        return (cx + (151 * math.cos(theta) - 7 * math.sin(theta)) * scale,
                cy + (-151 * math.sin(theta) - 7 * math.cos(theta)) * scale)

    def _water(self, image, t, level=1090):
        layer = Image.new('RGBA', image.size)
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((68, level, 1012, 1380), radius=30, fill=(11, 69, 78, 155))
        wave = [(x, level + 4 * math.sin(x / 95 + t * .6)) for x in range(68, 1013, 4)]
        d.line(wave, fill=(151, 225, 230, 230), width=4)
        for row in range(3):
            y = level + 70 + row * 80
            pts = [(x, y + 8 * math.sin(x / 140 + t * .35 + row)) for x in range(90, 992, 5)]
            d.line(pts, fill=(93, 177, 188, 45), width=2)
        return Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')

    def _jet(self, image, start, end, t):
        """One qualitative spitting action, without measured force or timing."""
        cycle = (t * .42) % 1
        if not .12 < cycle < .72:
            return
        progress = nature.clamp((cycle - .12) / .30)
        fade = min(1., (cycle - .12) * 10, (.72 - cycle) * 10)
        layer = Image.new('RGBA', image.size)
        d = ImageDraw.Draw(layer)
        points = []
        for index in range(36):
            q = index / 35 * progress
            x = start[0] + (end[0] - start[0]) * q
            y = start[1] + (end[1] - start[1]) * q - 24 * math.sin(q * math.pi)
            points.append((x, y))
        d.line(points, fill=(176, 239, 245, round(220 * fade)), width=9)
        d.line(points, fill=(245, 255, 255, round(180 * fade)), width=3)
        if progress > .94:
            for j in range(7):
                a = j * math.tau / 7
                r = 8 + (cycle - .42) * 70
                x, y = end[0] + r * math.cos(a), end[1] + r * math.sin(a)
                d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(191, 242, 246, round(200 * fade)))
        image.paste(Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB'))

    def _face(self, image, cx, cy, variant=0, scale=1., masked=False):
        """Abstract neutral faces, clearly not the paper's actual photographs."""
        d = ImageDraw.Draw(image)
        w, h = 94 * scale, 126 * scale
        skin = '#c2cbc7' if masked else '#d3bda5'
        d.ellipse((cx - w, cy - h, cx + w, cy + h), fill=skin, outline='#e3e8df', width=3)
        gap = (33 + (variant % 3) * 7) * scale
        eye_y = cy - (28 + (variant % 2) * 6) * scale
        for side in (-1, 1):
            x = cx + side * gap
            d.arc((x - 14 * scale, eye_y - 8 * scale, x + 14 * scale, eye_y + 9 * scale),
                  180, 360, fill='#384b48', width=4)
            d.ellipse((x - 4 * scale, eye_y - 3 * scale, x + 4 * scale, eye_y + 5 * scale), fill='#243c39')
        nose = (19 + variant % 3 * 4) * scale
        d.line([(cx, cy - 10 * scale), (cx - 5 * scale, cy + nose), (cx + 9 * scale, cy + nose)],
               fill='#647771', width=4)
        mouth_w = (24 + variant % 3 * 8) * scale
        d.line((cx - mouth_w, cy + 60 * scale, cx + mouth_w, cy + 60 * scale), fill='#53655f', width=5)
        # Both experiments removed hair and clothing from their face stimuli.
        # These original schematic targets likewise carry no hair-like outline.

    def _target(self, image, cx, variant, label, sublabel='', masked=False):
        d = ImageDraw.Draw(image)
        d.rounded_rectangle((cx - 180, 620, cx + 180, 1020), radius=23,
                            fill='#18343a', outline='#6e9597', width=3)
        self._face(image, cx, 806, variant, masked=masked)
        self.type.text(image, label, cx, 1043, 29, nature.PAPER, weight=650, anchor='mt')
        if sublabel:
            self.type.text(image, sublabel, cx, 1084, 24, nature.MUTED, anchor='mt')

    def diagram(self, kind, t, p, shot=None):
        if kind not in SCENES:
            return super().diagram(kind, t, p, shot)
        if self.ep.get('doi') != DOI or self.ep['production'].get('scene_family') != FAMILY:
            raise ValueError('Archerfish scene used outside its reviewed paper')
        image = self.background.copy()
        d = ImageDraw.Draw(image)
        if kind == 'archer_hunt':
            # General hunting context from the focal article's introduction.
            d.line((85, 730, 955, 667), fill='#798b68', width=16)
            d.ellipse((728, 629, 777, 671), fill=nature.AMBER)
            for side in (-1, 1):
                d.ellipse((746 + side * 24 - 25, 619, 746 + side * 24 + 25, 642),
                          fill='#a9cec0', outline=nature.MUTED, width=2)
            image = self._water(image, t, 1060)
            mouth = self._fish(image, 390, 1210 + 3 * math.sin(t), 1.25, t, 28)
            self._jet(image, mouth, (752, 657), t)
            self.type.text(image, 'Water becomes a hunting tool', 540, 895, 36, nature.ICE, anchor='mm')
            self.type.text(image, 'Hunting illustration - not recorded behaviour', 540, 1410, 25, nature.MUTED, anchor='mm')
        elif kind in {'archer_task', 'archer_transfer'}:
            transfer = kind == 'archer_transfer'
            variant = 1 + int(t / 2.6) % 3 if transfer else 1
            self._target(image, 304, 0, 'Learned face', 'Not rewarded')
            self._target(image, 776, variant, 'New face' if transfer else 'Other face',
                         'Choose the alternative' if transfer else 'Rewarded choice')
            image = self._water(image, t, 1142)
            mouth = self._fish(image, 420, 1270, .97, t, 22)
            self._jet(image, mouth, (776, 909), t)
            self.type.text(image, 'Task illustration - not the actual face images', 540, 1410, 25, nature.MUTED, anchor='mm')
        elif kind == 'archer_controls':
            self._target(image, 304, 0, 'Same comparison', masked=True)
            self._target(image, 776, 2, 'Fewer easy cues', masked=True)
            for i, text in enumerate(('Colour removed', 'Outer head shape masked', 'Brightness standardized')):
                y = 1158 + i * 78
                reveal = motion.ease((t - i * .23) / .65)
                d = ImageDraw.Draw(image)
                d.line((169, y + 13, 181, y + 26, 204, y - 6), fill=nature.MINT, width=max(1, round(5 * reveal)))
                self.type.text(image, text, 230, y - 12, 32, nature.ICE, weight=650)
            self.type.text(image, 'Control illustration - not the actual stimuli', 540, 1410, 25, nature.MUTED, anchor='mm')
        elif kind == 'archer_result':
            self._face(image, 540, 860, 1, scale=1.65, masked=True)
            for i, (y, label) in enumerate(((795, 'Eyes'), (900, 'Nose'), (970, 'Mouth'))):
                q = motion.ease((t - i * .2) / .6)
                x = 744 + q * 50
                d.line((670, y, x, y), fill=nature.ICE, width=2)
                self.type.text(image, label, 816, y - 17, 29, nature.ICE)
            self.type.text(image, 'A learned visual distinction', 540, 1180, 44, nature.PAPER, face='display', anchor='mm')
            self.type.text(image, 'Which exact cues were used remains unresolved', 540, 1293, 27, nature.MUTED, anchor='mm')
            self.type.text(image, 'Conceptual feature labels - not a mechanism test', 540, 1410, 25, nature.MUTED, anchor='mm')
        elif kind == 'archer_scope':
            self.type.text(image, 'A laboratory learning task', 540, 680, 46, nature.ICE, face='display', anchor='mm')
            for i in range(4):
                self._fish(image, 194 + i * 230, 880 + 5 * math.sin(t + i), .49, t + i, 0)
            self.type.text(image, 'Small groups of trained fish', 540, 1045, 39, nature.PAPER, face='display', anchor='mm')
            self.type.block(image, 'Distinguishing face images\nis not recognising a person.', 540, 1180, 41,
                            nature.MUTED, width=910, face='display', anchor='mt', max_lines=2)
            self.type.text(image, 'Conceptual summary - no wild behaviour tested', 540, 1410, 25, nature.MUTED, anchor='mm')
        return image


def render(episode, voice, output, *, media_dir=None, qa_dir=None):
    validate_motion_spec(episode)
    namespace = dict(motion.render.__globals__)
    namespace.update(Visuals=Visuals, validate_motion_spec=validate_motion_spec)
    pipeline = types.FunctionType(motion.render.__code__, namespace, 'render_archer_pipeline',
                                  motion.render.__defaults__, motion.render.__closure__)
    result = pipeline(episode, voice, output, media_dir=media_dir, qa_dir=qa_dir)
    result['scene_family'] = FAMILY
    result['scene_doi'] = DOI
    return result
