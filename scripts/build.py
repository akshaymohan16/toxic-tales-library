#!/usr/bin/env python3
"""Build Toxic Tales from reviewed JSON. Offline rendering; no paid API calls."""
import hashlib, json, math, os, re, shutil, subprocess, tempfile, wave
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
MEDIA = SITE / 'media'
ALLOWED_REPO = 'akshaymohan16/toxic-tales-library'
BG, INK, LIME, MUTED, TEAL = '#06171e', '#f6f8ed', '#ccff2c', '#afc4c7', '#43c8c5'
CHECKS = ('full_text', 'design', 'findings', 'limitations', 'rights')


def run(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def font(size, bold=False):
    suffix = '-Bold' if bold else ''
    path = f'/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf'
    return ImageFont.truetype(path, size)


def text_box(d, text, xy, width, height, size=42, color=INK, bold=False):
    x, y = xy
    for s in range(size, 19, -1):
        f = font(s, bold)
        lines, line = [], ''
        for word in str(text).split():
            trial = (line + ' ' + word).strip()
            if d.textlength(trial, font=f) > width and line:
                lines.append(line); line = word
            else:
                line = trial
        if line: lines.append(line)
        leading = int(s * 1.35)
        if len(lines) * leading <= height and all(d.textlength(t, font=f) <= width for t in lines):
            for t in lines:
                d.text((x, y), t, font=f, fill=color); y += leading
            return
    raise ValueError('Text does not fit safely: ' + str(text)[:90])


def diagram(d, kind, y=600):
    # Deliberately schematic, qualitative graphics. No invented effect-size bars.
    if kind == 'fish':
        d.polygon([(265,y),(155,y-78),(155,y+78)], fill=TEAL)
        d.ellipse((240,y-64,570,y+64), fill=TEAL)
        d.ellipse((525,y-25,542,y-8), fill=BG)
        for x in range(300,480,40): d.ellipse((x,y-18,x+7,y-11),fill=LIME)
    elif kind == 'choice':
        d.line([(360,y-110),(360,y),(190,y+100)],fill=INK,width=8)
        d.line([(360,y),(530,y+100)],fill=TEAL,width=8)
        d.rounded_rectangle((85,y+105,295,y+170),12,outline=INK,width=3)
        d.rounded_rectangle((425,y+105,635,y+170),12,outline=TEAL,width=3)
        text_box(d,'CLEAN',(110,y+120),170,40,23)
        text_box(d,'DRUG WATER',(440,y+120),185,40,22,color=TEAL)
    elif kind == 'caveat':
        d.rounded_rectangle((205,y-100,515,y+115),25,outline=LIME,width=6)
        d.rectangle((349,y-57,371,y+33),fill=LIME)
        d.ellipse((348,y+55,372,y+79),fill=LIME)
    else:
        for j in range(5):
            pts=[(x,y+j*34+18*math.sin(x/65+j)) for x in range(85,640,5)]
            d.line(pts,fill=TEAL if j%2 else LIME,width=4)


def frame(ep, scene, index, count):
    im = Image.new('RGB',(720,1280),BG); d=ImageDraw.Draw(im)
    d.rectangle((45,125,675,129),fill=LIME)
    text_box(d,'TOXIC TALES',(45,66),560,55,38,LIME,True)
    text_box(d,scene['headline'],(45,170),625,245,49,INK,True)
    diagram(d,scene.get('kind','river'))
    d.rounded_rectangle((35,895,685,1150),18,fill='#102c35',outline='#355962',width=2)
    text_box(d,scene['speech'],(58,921),600,205,30,INK,True)
    text_box(d,f'{ep["id"]} | {index+1}/{count} | SCHEMATIC',(45,1190),625,40,20,MUTED)
    return im


def cover(ep):
    im=frame(ep,{'headline':ep['hook'],'speech':'Original research. Evidence and limitations in our source library.','kind':ep['scenes'][0].get('kind','river')},0,1)
    return im.resize((1080,1920),Image.Resampling.LANCZOS)


def carousel(ep):
    paths=[]
    for i,slide in enumerate(ep.get('slides',[])):
        im=Image.new('RGB',(1080,1350),BG);d=ImageDraw.Draw(im)
        text_box(d,'TOXIC TALES / BEHIND THE STUDY',(70,70),940,65,32,LIME,True)
        d.rectangle((70,155,1010,160),fill=LIME)
        text_box(d,slide['headline'],(70,205),925,325,68,INK,True)
        text_box(d,slide['body'],(70,590),920,455,42,INK)
        text_box(d,f'{ep["id"]} | {i+1}/{len(ep["slides"])} | @toxic_tales_eco',(70,1130),940,60,28,LIME,True)
        text_box(d,ep['citation'],(70,1225),940,65,24,MUTED)
        path=MEDIA/f'{ep["slug"]}_slide_{i+1:02}.jpg'
        im.save(path,quality=94);paths.append(path.name)
    return paths


def stamp(t):
    ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def video(ep):
    slug=ep['slug'];out=MEDIA/f'{slug}.mp4'
    with tempfile.TemporaryDirectory() as temp:
        tmp=Path(temp);chunks=[];srt=[];start=0.0
        for i,sc in enumerate(ep['scenes']):
            voice=tmp/f'{i}.wav';image=tmp/f'{i}.png';clip=tmp/f'{i}.mp4'
            run(['espeak','-v','en-us','-s','170','-p','46','-w',str(voice),sc['speech']])
            with wave.open(str(voice),'rb') as w: spoken=w.getnframes()/w.getframerate()
            duration=spoken+0.35
            frame(ep,sc,i,len(ep['scenes'])).save(image)
            # Slow drift keeps the explanatory still graphic readable.
            filt="scale=1080:1920,zoompan=z='min(zoom+0.00010,1.012)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=24,format=yuv420p"
            run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate','24','-i',str(image),'-i',str(voice),'-vf',filt,'-af','apad=pad_dur=0.35','-t',f'{duration:.3f}','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','26','-c:a','aac','-ar','44100','-ac','2','-b:a','96k','-movflags','+faststart',str(clip)])
            exact=json.loads(subprocess.check_output(['ffprobe','-v','quiet','-show_format','-of','json',str(clip)]))
            duration=float(exact['format']['duration'])
            chunks.append(f"file '{clip}'")
            srt += [str(i+1),f'{stamp(start)} --> {stamp(start+spoken)}',sc['speech'],''];start+=duration
        if not 20 <= start <= 75: raise ValueError(f'Reel duration is outside safety limits: {start:.1f}s')
        (tmp/'clips.txt').write_text('\n'.join(chunks))
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(tmp/'clips.txt'),'-c','copy','-movflags','+faststart',str(out)])
        (MEDIA/f'{slug}.srt').write_text('\n'.join(srt),encoding='utf-8')
    cover(ep).save(MEDIA/f'{slug}_cover.jpg',quality=94)


def validate(ep):
    required=('id','slug','title','hook','doi','paper_title','citation','summary','evidence_note','source_url','scenes')
    if any(not ep.get(k) for k in required): raise ValueError('Missing required source or editorial field')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,90}',ep['slug']): raise ValueError('Unsafe slug')
    if not re.fullmatch(r'10\.\d{4,9}/\S+',ep['doi']): raise ValueError('Invalid DOI syntax')
    if ep.get('review_status') != 'verified' or not all(ep.get('checks',{}).get(k) is True for k in CHECKS):
        raise ValueError('Evidence checklist is incomplete; these flags require a real full-text review')
    if not 5<=len(ep['scenes'])<=9: raise ValueError('Expected 5-9 scenes')
    for scene in ep['scenes']:
        if not scene.get('headline') or not scene.get('speech') or len(scene['speech'].split())>40: raise ValueError('Invalid scene')
    if ep.get('slides') and not 5<=len(ep['slides'])<=8: raise ValueError('Expected 5-8 carousel slides')
    for post in ep.get('posts',[]):
        when=datetime.fromisoformat(post['publication_date'])
        if when.tzinfo is None: raise ValueError('Post time needs UTC offset')
        if post['format'] not in ('REEL','CAROUSEL'): raise ValueError('Unsupported post type')
        if post['format']=='CAROUSEL' and not ep.get('slides'): raise ValueError('Missing carousel')
        if not post.get('caption') or len(post['caption'])>2200: raise ValueError('Invalid caption')
        if ep['doi'] not in post['caption']: raise ValueError('Every caption needs its DOI')


def main():
    actual=os.environ.get('GITHUB_REPOSITORY',ALLOWED_REPO)
    if actual!=ALLOWED_REPO: raise SystemExit('Blocked: repository is not the Toxic Tales allowlisted repository')
    MEDIA.mkdir(parents=True,exist_ok=True)
    cache_file=MEDIA/'render-cache.json'
    cache=json.loads(cache_file.read_text()) if cache_file.exists() else {}
    papers=[];queue=[];seen=set();post_ids=set()
    code=Path(__file__).read_bytes()
    for path in sorted((ROOT/'episodes').glob('*.json')):
        ep=json.loads(path.read_text(encoding='utf-8'))
        if ep.get('review_status')!='verified': continue
        validate(ep)
        if ep['slug'] in seen: raise ValueError('Duplicate episode slug')
        seen.add(ep['slug'])
        fingerprint=hashlib.sha256(code+path.read_bytes()).hexdigest()
        expected=[MEDIA/f'{ep["slug"]}.mp4',MEDIA/f'{ep["slug"]}_cover.jpg']
        expected += [MEDIA/f'{ep["slug"]}_slide_{i+1:02}.jpg' for i in range(len(ep.get('slides',[])))]
        if cache.get(ep['slug'])!=fingerprint or not all(p.exists() for p in expected):
            video(ep);carousel(ep);cache[ep['slug']]=fingerprint
        entry={k:ep.get(k) for k in ('id','slug','title','hook','doi','paper_title','citation','summary','evidence_note','source_url','tags')}
        entry['media']={'reel':f'media/{ep["slug"]}.mp4','cover':f'media/{ep["slug"]}_cover.jpg','slides':[f'media/{p.name}' for p in expected[2:]]}
        papers.append(entry)
        if ep.get('publication_enabled') is True:
            for post in ep.get('posts',[]):
                pid=post['id']
                if pid in post_ids: raise ValueError('Duplicate publication ID')
                post_ids.add(pid)
                queue.append({**post,'episode_id':ep['id'],'doi':ep['doi'],'source_slug':ep['slug'],'cover':entry['media']['cover'],'media':[entry['media']['reel']] if post['format']=='REEL' else entry['media']['slides'],'scientifically_reviewed':True,'is_ai_generated':ep.get('is_ai_generated',False)})
    if sum(p.stat().st_size for p in SITE.rglob('*') if p.is_file())>900_000_000:
        raise RuntimeError('Pause: site is approaching its free hosting storage budget')
    for name,data in [('papers.json',papers),('publish-queue.json',queue)]:
        (SITE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    cache_file.write_text(json.dumps(cache,indent=2))
    (SITE/'.nojekyll').touch()
    (SITE/'health.json').write_text(json.dumps({'repository':ALLOWED_REPO,'built_at':datetime.now(timezone.utc).isoformat(),'commit':os.environ.get('GITHUB_SHA','local'),'episodes':len(papers),'queue_count':len(queue),'renderer':'offline-espeak-ffmpeg','note':'Build health is not proof of public deployment or Instagram publication.'},indent=2))
    print(f'Built {len(papers)} research entries and {len(queue)} publication candidates.')

if __name__=='__main__': main()
