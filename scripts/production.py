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
VERSION='science-journalism-5.0'
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
def norm(s):return re.findall(r"[a-z0-9]+",s.lower())

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
            print(f'{ep["id"]}: synthesizing and aligning segment {i+1}',flush=True)
            speed=1.03 if ep['production'].get('editorial_style')=='science-journalism' else 1.07
            audio,sr=self.tts.create(s['speech'],voice='af_heart',speed=speed,lang='en-us')
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
        for a,b in zip(captions,captions[1:]):
            a['end']=min(a['end'],b['start'])
            if a['end']<=a['start']:raise ValueError('Invalid caption alignment')
        all_audio=np.concatenate(audios);sf.write(out/'narration.wav',all_audio,sr)
        return timeline,captions,audit,cursor

class Visuals:
    def __init__(self,ep,out):
        self.ep=ep;self.out=out;self.assets={};self.frames={}
        for a in ep['production']['assets']:
            asset_key=hashlib.sha256(a['url'].encode()).hexdigest()[:12]+'-'+a['filename']
            path=download(a['url'],CACHE/'assets'/asset_key)
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
    def story_frame(self,shot,t,caption='',progress=0):
        """A narration-led film: organism imagery and explanatory sequences, not slides."""
        typ=shot['kind'];local=t-shot['start'];phase=max(0,min(1,local/max(.01,shot['end']-shot['start'])))
        natural=typ in ('nature','specimen','micro')
        if shot.get('asset'):
            im=self.picture(shot['asset'],local+shot.get('offset',0),wide=False)
            if not natural:im=Image.blend(im,Image.new('RGB',(W,H),'#071b23'),.83)
        else:im=Image.new('RGB',(W,H),'#071b23')
        # Quiet dark margins retain phone legibility without shrinking the organism.
        overlay=Image.new('RGBA',(W,H));od=ImageDraw.Draw(overlay)
        for y in range(H):
            alpha=int(175*max(0,1-y/360)+225*max(0,(y-780)/500))
            od.line((0,y,W,y),fill=(3,13,19,min(235,alpha)))
        im=Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB');d=ImageDraw.Draw(im)
        d.text((48,76),'TOXIC TALES  /  ECOLOGY',font=font(18),fill=LIME)
        if shot.get('kicker'):d.text((48,118),shot['kicker'].upper(),font=font(19),fill=TEAL)
        if shot.get('title'):
            label(im,shot['title'],172,43,width=610,center=False,stroke=2 if natural else 0)

        def text_at(text,x,y,size=30,color=WHITE):
            d.text((x,y),text,font=font(size),fill=color,anchor='mm',stroke_width=1,stroke_fill=BG)
        def arrow(x1,y1,x2,y2,color=TEAL):
            d.line((x1,y1,x2,y2),fill=color,width=5)
            ang=math.atan2(y2-y1,x2-x1);length=16
            d.polygon([(x2,y2),(x2-length*math.cos(ang-.5),y2-length*math.sin(ang-.5)),(x2-length*math.cos(ang+.5),y2-length*math.sin(ang+.5))],fill=color)
            q=(local*.40)%1;xx=x1+(x2-x1)*q;yy=y1+(y2-y1)*q
            d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=WHITE)
        def algae(cx,cy):
            for k in range(9):
                a=k*2.399;radius=12+9*math.sqrt(k);xx=cx+radius*math.cos(a+local*.08);yy=cy+radius*.6*math.sin(a+local*.08)
                d.ellipse((xx-10,yy-14,xx+10,yy+14),fill='#98ce58',outline=LIME,width=2)
        def plankter(cx,cy,scale=1):
            cy+=math.sin(local*2.0)*7
            d.ellipse((cx-35*scale,cy-52*scale,cx+35*scale,cy+46*scale),fill='#246673',outline=TEAL,width=3)
            d.ellipse((cx+5*scale,cy-34*scale,cx+13*scale,cy-26*scale),fill=WHITE)
            for side in (-1,1):
                d.line((cx,cy-40*scale,cx+side*50*scale,cy-75*scale,cx+side*70*scale,cy-67*scale),fill=TEAL,width=3)
                for k in range(3):d.line((cx+side*25*scale,cy+k*12*scale,cx+side*(48+math.sin(local*5+k)*8)*scale,cy+(k*12+20)*scale),fill=TEAL,width=2)

        if typ=='foodweb':
            fish(d,250+math.sin(local)*13,350,1.6,TEAL);text_at('Fish',475,350,33)
            plankter(250,570,1.0);text_at('Zooplankton',485,563,31)
            algae(250,775);text_at('Algae',477,765,33,LIME)
            arrow(250,716,250,642,LIME);arrow(250,484,250,409,TEAL)
            text_at('Many graze algae',485,610,21,'#c7dfcb')
        elif typ=='wastewater_route':
            x=145
            d.rectangle((x-42,310,x+42,370),fill='#28444d',outline=TEAL,width=3)
            d.polygon([(x-57,310),(x,268),(x+57,310)],fill='#28444d',outline=TEAL)
            d.rectangle((x-10,340,x+10,370),fill=TEAL)
            text_at('Medicine use',446,328,33)
            arrow(x,392,x,454)
            d.rounded_rectangle((x-60,477,x+60,557),14,fill='#28444d',outline=TEAL,width=3)
            d.line((x-48,514,x+48,514),fill=TEAL,width=4)
            for xx in (x-36,x,x+36):d.line((xx,487,xx,545),fill='#547d85',width=2)
            text_at('Wastewater',465,500,31);text_at('treatment',465,541,31)
            arrow(x,581,x,652)
            text_at('Some residues',455,616,23,RED)
            for k in range(4):
                pts=[(65+j*8,710+k*27+9*math.sin(j*.32+local+k)) for j in range(69)]
                d.line(pts,fill=TEAL if k%2==0 else '#3a8396',width=4)
            text_at('Freshwater',430,833,31)
            # Only a subset takes the downstream route; no quantitative removal rate.
            for k in range(3):
                q=((local*.15+k/3)%1);yy=380+q*385
                if k==1 and yy>550:continue
                xx=x+math.sin(q*10+k)*11
                d.ellipse((xx-6,yy-6,xx+6,yy+6),fill=RED)
        elif typ=='restoration_question':
            fish(d,405-590*min(1,phase*1.15),370,2,TEAL)
            text_at('Fish removed',440,443,29,TEAL)
            plankter(230,660,1.35);algae(472,690)
            for k in range(8):
                xx=100+k*74+10*math.sin(local+k);yy=530+100*math.sin(k*1.8+local*.4)
                d.ellipse((xx-6,yy-6,xx+6,yy+6),fill=RED)
            text_at(shot.get('pressure_label','Fluoxetine continues'),360,808,31,RED)
        elif typ=='evidence_rebound':
            text_at('After fish removal',360,340,31,TEAL)
            d.line((90,414,630,414),fill='#315967',width=2)
            text_at('No fluoxetine',360,469,32,WHITE)
            text_at('Stronger rebound',360,521,37,TEAL)
            d.line((90,594,630,594),fill='#315967',width=2)
            text_at('Fluoxetine continued',360,650,32,WHITE)
            text_at('Smaller rebound',360,702,37,RED)
            text_at('Zooplankton abundance',360,814,25,'#c9dadd')
        elif typ=='tanks':
            for col,(name,color) in enumerate([('Control',TEAL),('Low',LIME),('Higher',RED)]):
                x=140+col*220;text_at(name,x,353,27,color)
                for row in range(4):
                    y=435+row*87;d.ellipse((x-74,y-29,x+74,y+29),fill='#163742',outline=color,width=2)
                    fish(d,x+math.sin(local*1.6+row+col)*19,y,.55,color)
            text_at('12 outdoor communities',360,820,28)
        elif typ=='timeline':
            for k,txt in enumerate(('Fish introduced','Fluoxetine begins','Fish removed')):
                yy=380+k*145;d.ellipse((86,yy-11,108,yy+11),fill=TEAL)
                if k<2:d.line((97,yy+14,97,yy+130),fill=TEAL,width=3)
                d.text((135,yy),txt,font=font(32),fill=WHITE,anchor='lm')
            d.line((625,525,625,760),fill=RED,width=7)
            label(im,'Drug exposure continues',803,29,RED)
        elif typ=='limit':
            for k,item in enumerate(shot['items']):
                yy=410+k*150;d.line((35,yy-14,35,yy+64),fill=RED,width=4)
                label(im,item,yy,32,width=580,center=False)
        elif typ=='story_close':
            label(im,shot.get('takeaway',self.ep['production'].get('takeaway','Recovery depends on what remains.')),365,50,width=600)
            d.line((52,714,668,714),fill=TEAL,width=2)
            label(im,self.ep['citation'],752,21,TEAL,width=610,center=False)
            label(im,self.ep['doi'],812,23,WHITE,width=610,center=False)
        elif typ not in ('nature','specimen','micro'):
            raise ValueError('Unsupported journalism scene: '+typ)

        if shot.get('note'):
            label(im,shot['note'],873,18,'#d2dfe2',width=620,center=False,stroke=1)
        if caption:
            lines=wrap(caption,44,616)
            if len(lines)>3:raise ValueError('Story caption exceeds 3 safe lines: '+caption)
            cy=1025-(len(lines)-1)*26
            box=Image.new('RGBA',(W,H));bd=ImageDraw.Draw(box)
            bd.rounded_rectangle((33,cy-22,687,cy+len(lines)*56+12),15,fill=(2,12,18,210))
            im=Image.alpha_composite(im.convert('RGBA'),box).convert('RGB');d=ImageDraw.Draw(im)
            for k,line in enumerate(lines):d.text((360,cy+k*56),line,font=font(44),fill=WHITE,anchor='mt')
        d.rectangle((48,1220,48+int(624*progress),1223),fill=TEAL)
        return im

    def frame(self,shot,t,caption='',progress=0):
        if self.ep['production'].get('editorial_style')=='science-journalism':
            return self.story_frame(shot,t,caption,progress)
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
                y=390+i*150;d.ellipse((77,y-14,105,y+14),fill=LIME if phase>i/3 else '#3b6872')
                if i<2:d.line((91,y+16,91,y+135),fill='#4c747b',width=4)
                d.text((130,y),item,font=font(35),fill=WHITE,anchor='lm')
            d.line((610,532,610,532+int(253*min(1,phase*1.5))),fill=RED,width=12)
            label(im,'Drug dosing continues',810,31,RED)
        elif typ=='rebound':
            label(im,'After fish removal',350,33,TEAL)
            for i,(name,detail,color) in enumerate([('Controls','Stronger rebound',TEAL),('Drug-exposed','Smaller rebound',RED)]):
                y=440+i*190;rounded(d,(55,y,665,y+155),outline=color)
                label(im,name,y+21,28,color);label(im,detail,y+73,36)
            label(im,'Zooplankton abundance',815,29)
        elif typ=='limit':
            for i,item in enumerate(shot['items']):
                y=390+i*145;rounded(d,(58,y,662,y+115),outline=RED if i==min(len(shot['items'])-1,int(phase*len(shot['items']))) else '#3b6872')
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
    bounds=(45,95) if ep['production'].get('editorial_style')=='science-journalism' else (30,55)
    if not bounds[0]<=duration<=bounds[1]:raise ValueError(f'Film duration outside {bounds}: {duration}')
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
    if ep['production'].get('editorial_style')=='science-journalism':
        cover=vis.picture(ep['production']['cover_asset'],t=5,wide=False)
        shade=Image.new('RGBA',(W,H));sd=ImageDraw.Draw(shade)
        for y in range(H):
            alpha=int(205*max(0,1-y/690)+235*max(0,(y-700)/580))
            sd.line((0,y,W,y),fill=(3,13,19,min(240,alpha)))
        cover=Image.alpha_composite(cover.convert('RGBA'),shade).convert('RGB')
        label(cover,ep['production'].get('cover_kicker','TOXIC TALES / ECOLOGY'),115,22,LIME,center=False)
        label(cover,ep['production']['cover_title'],245,54,width=610,center=False,stroke=2)
        label(cover,ep['citation'],980,22,TEAL,width=610,center=False)
        label(cover,ep['doi'],1070,24,WHITE,center=False)
    else:
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
        if i in (0,len(ep['slides'])-1) and y<570:
            with Image.open(vis.assets[ep['production']['cover_asset']]) as ref:
                art=ImageOps.contain(ref.convert('RGB'),(590,180))
            canvas.paste(art,((720-art.width)//2,590))
        elif i==1 and y<610:
            for col,color in enumerate([TEAL,LIME,RED]):
                for row in range(4):
                    x=155+col*205;yy=620+row*36
                    rounded(d,(x-64,yy-13,x+64,yy+13),outline=color,r=7)
                    fish(d,x,yy,.38,color)
        elif i==2 and y<650:
            for k in range(4):
                x=120+k*160;rounded(d,(x-60,650,x+60,750),outline=TEAL,r=12)
                fish(d,x,687,.6,LIME);d.text((x,725),f'Test {k+1}',font=font(19),fill=WHITE,anchor='mm')
        elif i in (3,4,5) and y<620:
            phrases={3:'No clear difference is not proof of equality.',4:'One trait is not an entire personality.',5:'Experimental tanks are not whole ecosystems.'}
            rounded(d,(52,650,668,774),outline=TEAL)
            label(canvas,phrases[i],670,29,TEAL,width=550)
        d.line((52,803,668,803),fill=TEAL,width=2)
        d.text((52,830),ep['doi'],font=font(22),fill=TEAL)
        canvas.resize((1080,1350),Image.Resampling.LANCZOS).save(MEDIA/f'{ep["slug"]}_slide_{i+1:02}.jpg',quality=95)
    manifest={'renderer':VERSION,'duration':float(info['format']['duration']),'shots':timeline,'captions':captions,'segment_audio':audit,'final_audio_transcript':transcript,'final_script_similarity':similarity,'loudness':loud,'technical_passed':True,'editorial_review_required':True,'listening_review_claimed':False,'contact_sheet':f'qa/{ep["id"].lower()}-contact.jpg','asset_receipts':[{**a,'download_sha256':sha(vis.assets[a['id']])} for a in ep['production']['assets']]}
    manifest['editorial_style']=ep['production'].get('editorial_style','legacy')
    manifest['voice']={'model':'Kokoro v1.0','voice':'af_heart','speed':1.03 if ep['production'].get('editorial_style')=='science-journalism' else 1.07}
    return manifest
