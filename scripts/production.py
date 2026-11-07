"""Toxic Tales v4: reproducible neural narration and shot-based editorial films.

No paid APIs, direct eSpeak voice, generic fallback, or publishing credentials.
"""
import difflib, hashlib, json, math, os, re, subprocess, time
from pathlib import Path
from urllib.request import Request, urlopen
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'site/media'; QA=ROOT/'site/qa'; CACHE=ROOT/'render-cache'
W,H,FPS=720,1280,24
BG='#071c24'; WHITE='#fffdf2'; LIME='#cefa4c'; RED='#ff825f'; TEAL='#6bd6ce'
VERSION='neural-editorial-4.0'
FONTS=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('C:/Windows/Fonts/arial.ttf')]
FONT=next((x for x in FONTS if x.exists()),FONTS[0])
BOLD=FONT.with_name('DejaVuSans-Bold.ttf') if FONT.name.startswith('DejaVu') else FONT.with_name('arialbd.ttf')
ITALIC=FONT.with_name('DejaVuSans-BoldOblique.ttf') if FONT.name.startswith('DejaVu') else FONT.with_name('arialbi.ttf')

def sh(args):
    return subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def font(size,bold=True,italic=False): return ImageFont.truetype(str(ITALIC if italic else BOLD if bold else FONT),size)
def download(url,path,expected=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and (not expected or sha(path)==expected):return path
    for attempt in range(4):
        try:
            req=Request(url,headers={'User-Agent':'ToxicTalesResearch/4.0 (educational media; open licences)'})
            with urlopen(req,timeout=90) as r:path.write_bytes(r.read())
            if expected and sha(path)!=expected:raise ValueError('Model checksum mismatch')
            return path
        except Exception:
            if attempt==3:raise
            time.sleep(4*(attempt+1))
def wrap(text,size,width=600,bold=True):
    draw=ImageDraw.Draw(Image.new('RGB',(1,1)));lines=[];line=''
    for word in text.split():
        trial=(line+' '+word).strip()
        if draw.textlength(trial,font=font(size,bold))>width and line:lines.append(line);line=word
        else:line=trial
    if line:lines.append(line)
    return lines
def label(im,text,y,size=32,color=WHITE,width=600,center=True,bold=True,stroke=0):
    lines=wrap(text,size,width,bold);d=ImageDraw.Draw(im)
    for i,line in enumerate(lines):
        x=W/2 if center else 52
        d.text((x,y+i*(size+10)),line,font=font(size,bold),fill=color,anchor='mt' if center else 'lt',stroke_width=stroke,stroke_fill='#071015')
    return y+len(lines)*(size+10)
def fish(d,x,y,s=1,color=TEAL):
    d.ellipse((x-28*s,y-13*s,x+28*s,y+13*s),fill=color)
    d.polygon([(x-20*s,y),(x-42*s,y-19*s),(x-42*s,y+19*s)],fill=color)
    d.ellipse((x+14*s,y-5*s,x+19*s,y),fill=BG)
def rounded(d,box,fill='#15343e',outline=None,width=2,r=22):d.rounded_rectangle(box,r,fill,outline,width)
def norm(s):return re.findall(r"[a-z0-9]+",s.lower().replace(''',"'"))

class Voice:
    def __init__(self):
        from kokoro_onnx import Kokoro
        from faster_whisper import WhisperModel
        model=download('https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx',CACHE/'models/kokoro.onnx','7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5')
        voices=download('https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin',CACHE/'models/voices.bin','bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d')
        self.tts=Kokoro(str(model),str(voices))
        self.asr=WhisperModel('small.en',device='cpu',compute_type='int8',download_root=str(CACHE/'models/whisper'),cpu_threads=2)
    def make(self,ep,out):
        import soundfile as sf
        audios=[];timeline=[];captions=[];audit=[];cursor=0
        for i,s in enumerate(ep['production']['segments']):
            audio,sr=self.tts.create(s['speech'],voice='af_heart',speed=1.07,lang='en-us')
            audio=np.pad(audio,(0,int(sr*.13)))
            wav=out/f'voice-{i:02}.wav';sf.write(wav,audio,sr)
            segments,_=self.asr.transcribe(str(wav),beam_size=5,word_timestamps=True,condition_on_previous_text=False)
            words=[w for seg in segments for w in (seg.words or [])]
            heard=' '.join(w.word for w in words)
            ratio=difflib.SequenceMatcher(None,norm(s['speech']),norm(heard)).ratio()
            if ratio<.86:raise ValueError(f'Voice transcription mismatch {ep["id"]}/{i}: {heard}')
            target=norm(s['speech']);observed=[];times=[]
            for w in words:
                for token in norm(w.word):observed.append(token);times.append((w.start,w.end))
            matched={}
            for b in difflib.SequenceMatcher(None,target,observed).get_matching_blocks():
                for k in range(b.size):matched[b.a+k]=times[b.b+k]
            duration=len(audio)/sr;pos=0
            for c in s['captions']:
                n=len(norm(c));indices=range(pos,pos+n)
                available=[matched[j] for j in indices if j in matched]
                start=available[0][0] if available else duration*pos/len(target)
                end=available[-1][1] if available else duration*(pos+n)/len(target)
                captions.append({'start':cursor+max(0,start-.06),'end':cursor+min(duration,end+.16),'text':c})
                pos+=n
            assert pos==len(target),'Caption/script word mismatch'
            for shot in s['shots']:
                start=cursor+duration*shot.get('start',0);end=cursor+duration*shot.get('end',1)
                timeline.append({**shot,'start':start,'end':end,'segment':i})
            audit.append({'segment':i,'script':s['speech'],'transcript':heard,'token_similarity':round(ratio,4),'duration':round(duration,3)})
            audios.append(audio);cursor+=duration
        all_audio=np.concatenate(audios);sf.write(out/'narration.wav',all_audio,sr)
        return timeline,captions,audit,cursor

class Visuals:
    def __init__(self,ep,out):
        self.ep=ep;self.out=out;self.assets={};self.frames={}
        for a in ep['production']['assets']:
            path=download(a['url'],CACHE/'assets'/a['filename'])
            self.assets[a['id']]=path
    def picture(self,key,t=0,wide=False):
        p=self.assets[key]
        if p.suffix.lower() in ('.webm','.ogv','.mp4'):
            folder=self.out/('frames-'+key)
            if key not in self.frames:
                folder.mkdir(exist_ok=True)
                sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',p,'-t','18','-vf','fps=12,scale=960:-2',folder/'%05d.jpg'])
                self.frames[key]=sorted(folder.glob('*.jpg'))
            fs=self.frames[key];p=fs[int(t*12)%len(fs)]
        with Image.open(p) as original:src=original.convert('RGB')
        if wide:
            im=ImageOps.fit(src,(W,H)).filter(ImageFilter.GaussianBlur(22));im=Image.blend(im,Image.new('RGB',(W,H),BG),.65)
            fg=ImageOps.contain(src,(W,650));im.paste(fg,((W-fg.width)//2,290+(650-fg.height)//2))
        else:im=ImageOps.fit(src,(W,H),centering=(.5,.5))
        return im
    def frame(self,shot,t,caption='',progress=0):
        typ=shot['kind'];local=t-shot['start'];phase=local/max(.01,shot['end']-shot['start'])
        natural=typ in ('nature','specimen','micro')
        if natural:im=self.picture(shot['asset'],local+shot.get('offset',0),wide=(typ!='nature'))
        else:im=Image.new('RGB',(W,H),BG)
        d=ImageDraw.Draw(im)
        if natural:
            mask=Image.new('RGBA',(W,H));md=ImageDraw.Draw(mask)
            for y in range(H):
                alpha=int(155*max(0,1-y/340)+190*max(0,(y-770)/510))
                md.line((0,y,W,y),fill=(4,15,20,min(225,alpha)))
            im=Image.alpha_composite(im.convert('RGBA'),mask).convert('RGB');d=ImageDraw.Draw(im)
        label(im,'TOXIC TALES',95,21,LIME)
        if shot.get('title'):label(im,shot['title'],182,42,width=610,stroke=2 if natural else 0)
        if typ=='tanks':
            for col,(name,color) in enumerate([('Control',TEAL),('Low',LIME),('Higher',RED)]):
                x=142+col*218;d.text((x,365),name,font=font(29),fill=color,anchor='mm')
                for row in range(4):
                    y=435+row*88;rounded(d,(x-80,y-30,x+80,y+30),outline=color,r=12)
                    fish(d,x+math.sin(t*1.6+row+col)*16,y,.6,color)
            label(im,'4 independent tanks per treatment',820,27,WHITE)
        elif typ=='tracking':
            for i in range(4):
                x=60+(i%2)*310;y=340+(i//2)*215
                rounded(d,(x,y,x+285,y+190),outline='#3b6872')
                d.text((x+20,y+18),f'TEST 0{i+1}',font=font(20),fill=TEAL)
                pts=[(x+60+170*k/30,y+100+38*math.sin(k/7+i)) for k in range(max(2,int(31*phase)))]
                d.line(pts,fill=TEAL,width=3);fx,fy=pts[-1];fish(d,fx,fy,.65,LIME)
            label(im,'Same fish, tested repeatedly',800,30)
        elif typ=='result':
            rows=shot['rows']
            for i,(a,b) in enumerate(rows):
                y=365+i*210;rounded(d,(52,y,668,y+175),outline=TEAL if i==0 else LIME)
                label(im,a,y+22,29,TEAL if i==0 else LIME)
                label(im,b,y+79,38,width=550)
        elif typ=='timeline':
            items=['Fish added','Drug begins','Fish removed']
            for i,item in enumerate(items):
                y=390+i*150;d.ellipse((77,y-14,105,y+14),fill=LIME if i==2 else TEAL)
                if i<2:d.line((91,y+16,91,y+135),fill='#4c747b',width=4)
                d.text((130,y),item,font=font(35),fill=WHITE,anchor='lm')
            d.line((610,532,610,785),fill=RED,width=12)
            label(im,'Drug dosing continues',810,31,RED)
        elif typ=='rebound':
            label(im,'After fish removal',350,33,TEAL)
            for i,(name,detail,color) in enumerate([('Controls','Stronger rebound',TEAL),('Drug-exposed','Smaller rebound',RED)]):
                y=440+i*190;rounded(d,(55,y,665,y+155),outline=color)
                label(im,name,y+21,28,color);label(im,detail,y+73,36)
            label(im,'Zooplankton abundance',815,29)
        elif typ=='limit':
            for i,item in enumerate(shot['items']):
                y=390+i*145;rounded(d,(58,y,662,y+115),outline=RED if i==0 else '#3b6872')
                label(im,item,y+25,32,width=550)
        elif typ=='closing':
            label(im,'REAL SCIENCE.',410,52,LIME);label(im,'DARK TWISTS.',490,52)
            label(im,'@toxic_tales_eco',680,30,TEAL)
        if shot.get('note'):label(im,shot['note'],850,20,'#b9d2d6',width=620,stroke=1 if natural else 0)
        if caption:
            lines=wrap(caption,44,590)
            if len(lines)>3:raise ValueError('Caption exceeds 3 safe lines: '+caption)
            y=945-(len(lines)-1)*26
            for i,line in enumerate(lines):
                d.text((350,y+i*55),line,font=font(44,italic=True),fill=WHITE,anchor='mt',stroke_width=4,stroke_fill='#051318')
        d.rectangle((52,1126,52+int(580*progress),1130),fill=LIME)
        return im

def render(ep,voice,out):
    timeline,captions,audit,duration=voice.make(ep,out)
    if not 30<=duration<=55:raise ValueError(f'Film duration outside 30-55s: {duration}')
    if max(s['end']-s['start'] for s in timeline)>7.5:raise ValueError('Shot too long')
    vis=Visuals(ep,out);silent=out/'picture.mp4'
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-vf','scale=1080:1920:flags=lanczos','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',str(silent)]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    for i in range(math.ceil(duration*FPS)):
        t=i/FPS;shot=next((s for s in timeline if s['start']<=t<s['end']),timeline[-1])
        caption=next((c['text'] for c in captions if c['start']<=t<c['end']),'')
        proc.stdin.write(vis.frame(shot,t,caption,t/duration).tobytes())
    proc.stdin.close()
    if proc.wait()!=0:raise RuntimeError('Video encode failed')
    target=MEDIA/(ep['slug']+'.mp4')
    sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',silent,'-i',out/'narration.wav','-map','0:v:0','-map','1:a:0','-c:v','copy','-af','loudnorm=I=-16:TP=-2.5:LRA=7','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-shortest','-movflags','+faststart',target])
    info=json.loads(sh(['ffprobe','-v','quiet','-show_streams','-show_format','-of','json',target]).stdout)
    loud=sh(['ffmpeg','-hide_banner','-i',target,'-af','loudnorm=I=-16:TP=-2.5:LRA=7:print_format=json','-vn','-f','null','-']).stderr
    loud=json.loads(loud[loud.rfind('{'):loud.rfind('}')+1])
    if not -18<=float(loud['input_i'])<=-14 or float(loud['input_tp'])>-1:raise ValueError('Loudness/peak gate failed')
    final_segments,_=voice.asr.transcribe(str(target),beam_size=5,condition_on_previous_text=False)
    transcript=' '.join(s.text for s in final_segments)
    intended=' '.join(s['speech'] for s in ep['production']['segments'])
    similarity=difflib.SequenceMatcher(None,norm(intended),norm(transcript)).ratio()
    if similarity<.90:raise ValueError('Final encoded audio failed script comparison')
    for term in ep['production']['critical_terms']:
        if term.lower() not in transcript.lower():raise ValueError('Critical scientific term absent from final transcript: '+term)
    frames=[]
    for i,s in enumerate(timeline):
        name=f'{ep["id"].lower()}-shot-{i+1:02}.jpg';path=QA/name
        sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str((s['start']+s['end'])/2),'-i',target,'-frames:v','1','-vf','scale=360:640',path])
        with Image.open(path) as im:frames.append(im.copy())
    grid=Image.new('RGB',(1080,640*math.ceil(len(frames)/3)),BG)
    for i,im in enumerate(frames):grid.paste(im,((i%3)*360,(i//3)*640))
    grid.save(QA/(ep['id'].lower()+'-contact.jpg'),quality=91)
    cover=vis.picture(ep['production']['cover_asset'],wide=True)
    d=ImageDraw.Draw(cover);d.rectangle((0,0,W,270),fill=BG);d.rectangle((0,880,W,H),fill=BG)
    label(cover,'TOXIC TALES / '+ep['id'],90,22,LIME)
    label(cover,ep['production']['cover_title'],175,46)
    label(cover,ep['citation'],920,23,TEAL)
    label(cover,ep['doi'],1000,24)
    cover.resize((1080,1920),Image.Resampling.LANCZOS).save(MEDIA/(ep['slug']+'_cover.jpg'),quality=95)
    for i,s in enumerate(ep.get('slides',[])):
        canvas=Image.new('RGB',(720,900),BG);d=ImageDraw.Draw(canvas)
        d.text((48,45),f'TOXIC TALES  /  {i+1:02}  OF  {len(ep["slides"]):02}',font=font(20),fill=LIME)
        y=label(canvas,s['headline'],126,42,LIME,width=615,center=False)
        y+=45
        for line in wrap(s['body'],30,610,False):
            d.text((52,y),line,font=font(30,False),fill=WHITE);y+=43
        if y>765:raise ValueError('Carousel text overflow')
        d.line((52,803,668,803),fill=TEAL,width=2)
        d.text((52,830),ep['doi'],font=font(22),fill=TEAL)
        canvas.resize((1080,1350),Image.Resampling.LANCZOS).save(MEDIA/f'{ep["slug"]}_slide_{i+1:02}.jpg',quality=95)
    manifest={'renderer':VERSION,'duration':float(info['format']['duration']),'shots':timeline,'captions':captions,'segment_audio':audit,'final_audio_transcript':transcript,'final_script_similarity':similarity,'loudness':loud,'technical_passed':True,'editorial_review_required':True,'listening_review_claimed':False,'contact_sheet':f'qa/{ep["id"].lower()}-contact.jpg','asset_receipts':[{**a,'download_sha256':sha(vis.assets[a['id']])} for a in ep['production']['assets']]}
    return manifest
