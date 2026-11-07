#!/usr/bin/env python3
"""Check anonymous Pages downloads against the exact build; no paid services."""
import hashlib, json, os, re, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from PIL import Image, ImageDraw

REPO = 'akshaymohan16/toxic-tales-library'
BASE = 'https://akshaymohan16.github.io/toxic-tales-library/'
ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / 'expected-site'
OUT = ROOT / 'verification'
OUT.mkdir(exist_ok=True)
if os.environ.get('GITHUB_REPOSITORY') != REPO:
    raise SystemExit('Repository boundary violation')
COMMIT = os.environ['GITHUB_SHA']
report = {'repository': REPO, 'commit': COMMIT, 'checked_at': datetime.now(timezone.utc).isoformat(), 'anonymous': True, 'files': [], 'passed': False}

def get(path):
    if path.startswith('/') or '..' in Path(path).parts or '://' in path:
        raise ValueError('Unsafe relative path')
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(urljoin(BASE, path) + '?verify=' + COMMIT, headers={'User-Agent': 'ToxicTales-PublicMediaQA/1.0'}), timeout=60) as r:
        if r.status != 200 or not r.geturl().startswith(BASE):
            raise RuntimeError('Unexpected public response')
        data = r.read(100_000_001)
        if len(data) > 100_000_000:
            raise RuntimeError('Oversized public file')
        mime = r.headers.get_content_type()
    expected = EXPECTED / path
    if not expected.is_file() or hashlib.sha256(data).digest() != hashlib.sha256(expected.read_bytes()).digest():
        raise RuntimeError('Live/build mismatch: ' + path)
    target.write_bytes(data)
    report['files'].append({'path': path, 'url': urljoin(BASE,path), 'status': 200, 'bytes': len(data), 'content_type': mime, 'sha256': hashlib.sha256(data).hexdigest()})
    return target

try:
    last = None
    for attempt in range(8):
        try:
            get('health.json')
            health = json.loads((OUT/'health.json').read_text())
            if health['commit'] != COMMIT or health['repository'] != REPO:
                raise RuntimeError('Old deployment')
            break
        except Exception as e:
            last = e
            if attempt == 7:
                raise
            time.sleep(10)
    for p in ['index.html', 'papers.json', 'publish-queue.json']:
        get(p)
    papers = json.loads((OUT/'papers.json').read_text())
    for ep in papers:
        media = ep['media']
        cover = get(media['cover'])
        with Image.open(cover) as im:
            assert im.size == (1080,1920), 'Invalid cover dimensions'
        mp4 = get(media['reel'])
        info = json.loads(subprocess.check_output(['ffprobe','-v','quiet','-show_streams','-show_format','-of','json',str(mp4)]))
        v = next(s for s in info['streams'] if s['codec_type']=='video')
        a = next(s for s in info['streams'] if s['codec_type']=='audio')
        duration = float(info['format']['duration'])
        assert (v['width'],v['height']) == (1080,1920) and v['codec_name']=='h264'
        assert a['codec_name']=='aac' and 20 <= duration <= 75
        level = subprocess.run(['ffmpeg','-hide_banner','-i',str(mp4),'-af','volumedetect','-vn','-f','null','-'],capture_output=True,text=True,check=True).stderr
        match = re.search(r'mean_volume: ([-0-9.]+) dB',level)
        assert match and float(match.group(1)) > -55, 'Audio missing or too quiet'
        report['files'][-1]['duration_seconds'] = duration
        report['files'][-1]['video'] = 'h264 1080x1920'
        report['files'][-1]['audio'] = 'aac; mean volume ' + match.group(1) + ' dB'
        frames=[]
        for i in range(8):
            f=OUT/(ep['slug']+'_frame_'+str(i)+'.jpg')
            t=min(duration-.15,(i+.45)*duration/8)
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',str(mp4),'-frames:v','1','-vf','scale=360:640',str(f)],check=True)
            frames.append(f)
        grid=Image.new('RGB',(1440,1280),'white')
        for i,f in enumerate(frames):
            with Image.open(f) as im: grid.paste(im,((i%4)*360,(i//4)*640))
        grid.save(OUT/(ep['slug']+'_video_contact.jpg'),quality=92)
        slides=[]
        for p in media.get('slides',[]):
            f=get(p)
            with Image.open(f) as im:
                assert im.size == (1080,1350), 'Invalid carousel dimensions'
                slides.append(im.copy().resize((360,450)))
        if slides:
            grid=Image.new('RGB',(1080,450*((len(slides)+2)//3)),'white')
            for i,im in enumerate(slides):grid.paste(im,((i%3)*360,(i//3)*450))
            grid.save(OUT/(ep['slug']+'_carousel_contact.jpg'),quality=92)
    report['passed']=True
finally:
    (OUT/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':report['passed'],'commit':COMMIT,'checked_at':report['checked_at'],'public_files_verified':len(report['files'])}))

