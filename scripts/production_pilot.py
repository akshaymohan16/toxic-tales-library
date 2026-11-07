"""Toxic Tales v7: wildlife footage and original evidence illustrations.

No paid APIs, direct eSpeak voice, generic fallback, or publishing credentials.
"""
import difflib, hashlib, json, math, os, re, subprocess, time
from pathlib import Path
from functools import lru_cache
from urllib.request import Request, urlopen
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'site/media'; QA=ROOT/'site/qa'; CACHE=ROOT/'render-cache'
W,H,FPS=720,1280,24
BG='#071c24'; WHITE='#fffdf2'; LIME='#cefa4c'; RED='#ff825f'; TEAL='#6bd6ce'
VERSION='ecology-story-7.0'
FONTS=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('C:/Windows/Fonts/arial.ttf')]
FONT=next((x for x in FONTS if x.exists()),FONTS[0])
BOLD=FONT.with_name('DejaVuSans-Bold.ttf') if FONT.name.startswith('DejaVu') else FONT.with_name('arialbd.ttf')
ITALIC=FONT.with_name('DejaVuSans-BoldOblique.ttf') if FONT.name.startswith('DejaVu') else FONT.with_name('arialbi.ttf')

def sh(args):
    return subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
@lru_cache(maxsize=160)
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

NUMBER_TOKENS={word:str(i) for i,word in enumerate(
    ('one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'),1)}

def critical_tokens(text):
    """Only normalize punctuation/case and equivalent numbers; retain every word."""
    return [NUMBER_TOKENS.get(token,token) for token in norm(text)]

def require_critical_terms(transcript,terms):
    heard=critical_tokens(transcript)
    for term in terms:
        expected=critical_tokens(term)
        if not expected or not any(heard[i:i+len(expected)]==expected
                                   for i in range(len(heard)-len(expected)+1)):
            raise ValueError('Critical scientific term absent from final transcript: '+term)

def validate_text_layout(ep):
    """Fail before narration or rendering, using the same fonts and widths as frames."""
    for segment in ep['production']['segments']:
        for caption in segment['captions']:
            if len(wrap(caption,45,608))>2:
                raise ValueError('Use shorter caption phrases, max two lines: '+caption)
        for shot in segment['shots']:
            title=shot.get('title','')
            if len(wrap(title,shot.get('title_size',50),610))>3:
                raise ValueError('Headline too long: '+title)

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
            speed=float(ep['production'].get('voice_speed',1.00))
            if not .85<=speed<=1.12:raise ValueError('Voice speed outside natural narration range')
            audio,sr=self.tts.create(s['speech'],voice='af_heart',speed=speed,lang='en-us')
            audio=np.pad(audio,(0,int(sr*s.get('pause_after',.16))))
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


# This renderer is intentionally isolated from earlier, reviewed film versions.
# All schematics below are editorial illustrations, never simulated study footage.
class Visuals:
    def __init__(self,ep,out):
        self.ep=ep;self.out=out;self.assets={};self.frames={};self.asset_info={}
        for a in ep['production']['assets']:
            key=hashlib.sha256(a['url'].encode()).hexdigest()[:12]+'-'+a['filename']
            self.assets[a['id']]=download(a['url'],CACHE/'assets'/key,a.get('sha256'))
            self.asset_info[a['id']]=a
        yy,xx=np.mgrid[0:H,0:W]
        glow=np.exp(-(((xx-W*.5)/(W*.8))**2+((yy-H*.4)/(H*.7))**2)*3)
        arr=np.zeros((H,W,3),dtype=np.uint8)
        for k,(base,light) in enumerate(((3,5),(13,19),(16,17))):arr[:,:,k]=base+glow*light
        self.background=Image.fromarray(arr)

    def picture(self,key,t=0,focus=None,wide=False):
        p=self.assets[key];info=self.asset_info[key]
        cx,cy=focus or info.get('focus',[.5,.5])
        if p.suffix.lower() in ('.webm','.ogv','.mp4'):
            fkey=(key,round(cx,3),round(cy,3))
            if fkey not in self.frames:
                folder=self.out/('portrait-'+key+'-'+str(int(cx*1000))+'-'+str(int(cy*1000)))
                folder.mkdir(exist_ok=True)
                # Crop from native resolution before encoding portrait frames.
                # Never first shrink a landscape clip into a tiny vertical crop.
                vf=f'fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}:(in_w-out_w)*{cx}:(in_h-out_h)*{cy}'
                sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',p,'-t','45','-vf',vf,'-q:v','2',folder/'%05d.jpg'])
                self.frames[fkey]=sorted(folder.glob('*.jpg'))
                if not self.frames[fkey]:raise ValueError('No decoded frames: '+key)
            fs=self.frames[fkey];p=fs[int(max(0,t)*FPS)%len(fs)]
            with Image.open(p) as src:return src.convert('RGB')
        with Image.open(p) as src:
            # Gentle framing on an actual photograph, not fabricated animal motion.
            zoom=1.025+math.sin(t*.20)*.015
            im=ImageOps.fit(src.convert('RGB'),(int(W*zoom),int(H*zoom)),centering=(cx,cy))
            return ImageOps.fit(im,(W,H))

    def txt(self,im,txt,x,y,size=32,color=WHITE,anchor='mm',italic=False,stroke=0):
        ImageDraw.Draw(im).text((x,y),txt,font=font(size,italic=italic),fill=color,anchor=anchor,
                               stroke_width=stroke,stroke_fill='#02090c')

    def headline(self,im,txt,y=185,size=52,color=WHITE):
        if not txt:return
        lines=wrap(txt,size,610)
        if len(lines)>3:raise ValueError('Headline too long: '+txt)
        for j,line in enumerate(lines):self.txt(im,line,48,y+j*(size+4),size,color,'lt',stroke=1)

    def natural(self,shot,local):
        im=self.picture(shot['asset'],local+shot.get('offset',0),shot.get('focus'))
        layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer)
        for y in range(H):
            a=110*max(0,1-y/260)+175*max(0,(y-850)/430)
            if a:d.line((0,y,W,y),fill=(1,8,10,int(a)))
        return Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')

    def egg(self,im,x,y,r,t=0,embryo=True,alpha=255):
        """Stylised carp embryo with yolk and transparent chorion; explicitly schematic."""
        layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer)
        d.ellipse((x-r,y-r,x+r,y+r),fill=(159,207,193,int(alpha*.10)),outline=(222,246,224,int(alpha*.85)),width=max(1,int(r*.025)))
        d.arc((x-r+6,y-r+6,x+r-6,y+r-6),190,290,fill=(250,255,236,int(alpha*.65)),width=max(2,int(r*.035)))
        d.ellipse((x-r*.38,y-r*.28,x+r*.45,y+r*.51),fill=(221,183,83,int(alpha*.65)),outline=(252,219,132,alpha),width=2)
        if embryo:
            # A curved body, dark eye and slender tail help explain what is alive.
            pts=[]
            for i in range(35):
                a=-2.5+i/34*4.5
                rr=r*(.52+.025*math.sin(t*2+i*.12))
                pts.append((x+rr*math.cos(a),y+rr*.82*math.sin(a)))
            d.line(pts,fill=(156,179,164,alpha),width=max(3,int(r*.12)))
            hx,hy=pts[0];hr=r*.16
            d.ellipse((hx-hr,hy-hr,hx+hr,hy+hr),fill=(191,197,157,alpha))
            d.ellipse((hx-hr*.3,hy-hr*.48,hx+hr*.35,hy+hr*.17),fill=(6,22,24,alpha))
            for i in range(6,29,3):
                px,py=pts[i];d.ellipse((px-1.5,py-1.5,px+1.5,py+1.5),fill=(61,111,105,alpha))
        im.paste(Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB'))

    def larva(self,im,x,y,s,t=0,flip=False):
        d=ImageDraw.Draw(im);direc=-1 if flip else 1
        pts=[]
        for i in range(60):
            q=i/59;xx=x+direc*q*190*s
            yy=y+math.sin(t*5-q*7)*q*22*s
            pts.append((xx,yy))
        for j in range(59,0,-1):
            q=j/59;rad=(1-q)*10*s+1
            d.line([pts[j-1],pts[j]],fill='#a6c6ac',width=max(1,int(rad)))
        d.ellipse((x-22*s,y-13*s,x+24*s,y+14*s),fill='#b3c4a2',outline='#ecf1ce',width=2)
        d.ellipse((x-7*s,y+7*s,x+51*s,y+33*s),fill='#c7a35f',outline='#f1d488',width=2)
        ex=x-10*s if not flip else x+10*s
        d.ellipse((ex-6*s,y-6*s,ex+6*s,y+6*s),fill='#0a1515',outline='#f1efd4',width=1)

    def duck(self,im,x,y,s=1,t=0,flying=False):
        """Editorial silhouette. No claim to depict experimental animals."""
        d=ImageDraw.Draw(im)
        if flying:
            wing=55+32*math.sin(t*4)
            d.polygon([(x-9*s,y),(x-98*s,y-wing*s),(x-59*s,y-8*s),(x-17*s,y+11*s)],fill='#dce6cc')
            d.polygon([(x+10*s,y),(x+83*s,y-wing*.8*s),(x+62*s,y+5*s),(x+22*s,y+15*s)],fill='#9cbaa7')
            d.ellipse((x-37*s,y-13*s,x+48*s,y+17*s),fill='#a6bfa7')
            d.line((x+35*s,y,x+72*s,y-10*s),fill='#c6d1ad',width=max(4,int(13*s)))
            d.ellipse((x+61*s,y-22*s,x+86*s,y+2*s),fill='#4d8570')
            d.polygon([(x+84*s,y-14*s),(x+109*s,y-8*s),(x+84*s,y-5*s)],fill='#d6ba59')
        else:
            d.ellipse((x-82*s,y-27*s,x+70*s,y+44*s),fill='#9eae96')
            d.polygon([(x-68*s,y+11*s),(x-112*s,y-15*s),(x-85*s,y+30*s)],fill='#566f66')
            d.ellipse((x-35*s,y-13*s,x+34*s,y+29*s),fill='#647d70')
            d.line((x+48*s,y+5*s,x+57*s,y-60*s),fill='#c3c7ad',width=max(5,int(32*s)))
            d.ellipse((x+29*s,y-94*s,x+87*s,y-43*s),fill='#3b7e67')
            d.polygon([(x+81*s,y-77*s),(x+123*s,y-65*s),(x+82*s,y-60*s)],fill='#e4c264')
            d.ellipse((x+66*s,y-79*s,x+73*s,y-72*s),fill='#0a1618')
        return im

    def pond(self,im,cx,cy,rx,ry,t=0):
        d=ImageDraw.Draw(im)
        pts=[(cx+math.cos(k/60*2*math.pi)*rx*(1+.07*math.sin(k*.7)),cy+math.sin(k/60*2*math.pi)*ry*(1+.08*math.cos(k*.9))) for k in range(61)]
        d.polygon(pts,fill='#184d5c',outline='#6caaad',width=3)
        for j in range(4):
            yy=cy-ry*.55+j*ry*.35
            d.arc((cx-rx*.68+math.sin(t+j)*6,yy-5,cx+rx*.7,yy+8),0,175,fill='#458d96',width=2)

    def background_scene(self,shot,local,dim=.68):
        if shot.get('asset'):
            im=self.natural(shot,local)
            return Image.blend(im,self.background,dim)
        return self.background.copy()

    def frame(self,shot,t,caption='',progress=0):
        kind=shot['kind'];local=t-shot['start'];duration=max(.01,shot['end']-shot['start']);p=min(1,local/duration)
        natural=kind in ('duck','pond','feeding','scope','closing','nature','landscape')
        im=self.natural(shot,local) if natural and shot.get('asset') else self.background_scene(shot,local)
        d=ImageDraw.Draw(im)
        if kind in ('duck','feeding'):
            # One word of surprise or a precise label, while the animal remains dominant.
            if shot.get('inset_egg'):
                self.egg(im,560,690,83,local)
                self.txt(im,'FISH EGG',560,802,20,LIME)
                self.txt(im,'Illustration',560,827,16,'#d9e8df')
        elif kind=='question':
            # The geographic problem is shown without asserting a particular wild colonisation.
            self.pond(im,185,460,140,98,local);self.pond(im,535,770,140,98,local)
            self.larva(im,158,450,.42,local)
            for j in range(22):
                q=j/21;x=205+q*290;y=550+q*125
                d.line((x-5,y+7,x+5,y-7),fill='#617267',width=2)
            self.txt(im,'DRY LAND',357,629,29,'#e4d8ad')
            self.txt(im,'A possible route?',360,865,28,LIME)
        elif kind=='passage':
            # Avoid a made-up anatomical mechanism: demonstrate the tested sequence.
            self.duck(im,315,434,1.65,local)
            self.egg(im,176,310,43,local)
            self.txt(im,'EGGS EATEN',360,550,29,LIME)
            d.line((360,590,360,651),fill='#8ea99b',width=4)
            d.polygon([(350,640),(370,640),(360,657)],fill='#8ea99b')
            d.ellipse((235,696,485,747),fill='#172b2a',outline='#7e9d8c',width=2)
            for j in range(4):
                xx=295+j*44;yy=712+8*math.sin(j*2)
                d.ellipse((xx-15,yy-12,xx+15,yy+12),fill='#687253')
            self.txt(im,'DROPPINGS COLLECTED',360,798,26)
            self.txt(im,'Captive feeding experiment',360,855,23,'#bccfc6')
        elif kind=='eggs':
            # Actual count, no misleading visual ratio or simulated observations.
            for row in range(3):
                for col in range(6):self.egg(im,116+col*97,430+row*135,33,local,embryo=False)
            self.txt(im,'18',360,825,88,LIME)
            self.txt(im,'intact eggs recovered',360,899,28)
            if shot.get('show_denominator',True):self.txt(im,'from approximately 8,000 eggs fed',360,345,25,'#d0ded5')
        elif kind=='embryos':
            self.egg(im,360,585,198,local)
            self.txt(im,'A living embryo',360,848,35,LIME)
            self.txt(im,'inside a recovered egg',360,893,27)
        elif kind=='hatching':
            # Recovered eggs returned to water BEFORE hatching. Three schematic hatchlings.
            self.txt(im,'BACK IN WATER',360,347,27,'#bddcd9')
            for j in range(3):
                yy=465+j*144
                hatch=max(0,min(1,(p-.15)/.52))
                if hatch<.8:self.egg(im,250,yy,57,local,alpha=int(255*(1-hatch)))
                if hatch>.05:
                    self.larva(im,260+hatch*110+math.sin(local+j)*8,yy,.68,local+j)
            self.txt(im,'3 HATCHED',360,860,52,LIME)
            self.txt(im,'after incubation',360,907,23,'#bddcd9')
        elif kind=='connection':
            self.pond(im,187,740,143,102,local);self.pond(im,535,470,143,102,local)
            # Animated dotted flight route is an unmeasured possibility, not tracked data.
            for j in range(23):
                q=j/22;x=185+350*q;y=650-190*q-90*math.sin(q*math.pi)
                d.ellipse((x-3,y-3,x+3,y+3),fill='#a5d1bb')
            q=(p*.78+.08);x=185+350*q;y=650-190*q-90*math.sin(q*math.pi)
            self.duck(im,x,y,.7,local,True)
            self.txt(im,'POSSIBLE TRANSPORT',360,889,30,LIME)
        elif kind not in ('duck','pond','feeding','scope','closing','nature','landscape'):
            raise ValueError('Unsupported new-pilot shot kind: '+kind)

        self.txt(im,'TOXIC TALES',48,80,20,LIME,'lt',stroke=1)
        self.headline(im,shot.get('title',''),y=175,size=shot.get('title_size',50),color=shot.get('title_color',WHITE))
        if not natural:
            self.txt(im,'ILLUSTRATION',48,115,16,'#bdd2c6','lt')
        if caption:
            lines=wrap(caption,45,608)
            if len(lines)>2:raise ValueError('Use shorter caption phrases, max two lines: '+caption)
            y=1012-(len(lines)-1)*24
            # Outlined, readable phrases; no bouncing words or decorative sentence walls.
            layer=Image.new('RGBA',(W,H));ld=ImageDraw.Draw(layer)
            for yy in range(y-30,min(H,y+len(lines)*55+40)):
                a=max(0,1-abs(yy-(y+len(lines)*24))/(len(lines)*29+40))
                ld.line((0,yy,W,yy),fill=(0,5,7,int(a*120)))
            im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
            for j,line in enumerate(lines):
                color=LIME if any(w in line.lower() for w in ('still hatch','three hatched','living embryos','dry land')) else WHITE
                self.txt(im,line,350,y+j*55,45,color,'mt',italic=True,stroke=3)
        default_note=('Illustration; fungal losses occurred during incubation'
                      if kind=='hatching' else 'Reference footage' if natural
                      else 'Conceptual illustration; not study footage')
        note=shot.get('note',default_note)
        for j,line in enumerate(wrap(note,17,595,False)):
            self.txt(im,line,48,1147+j*22,17,'#e1ebe5','lt',stroke=1)
        ImageDraw.Draw(im).rectangle((48,1215,48+int(585*progress),1218),fill=LIME)
        return im

    def pilot_cover(self):
        im=self.picture(self.ep['production']['cover_asset'],self.ep['production'].get('cover_offset',4))
        layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer)
        for y in range(H):
            a=210*max(0,1-y/650)+230*max(0,(y-760)/520)
            d.line((0,y,W,y),fill=(0,8,10,int(min(235,a))))
        im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
        self.txt(im,'TOXIC TALES',48,93,24,LIME,'lt',stroke=1)
        titles=self.ep['production'].get('cover_lines',['EATEN BY A DUCK.','STILL HATCHED.'])
        y=206
        for i,txt in enumerate(titles):
            for line in wrap(txt,59,610):
                self.txt(im,line,47,y,59,LIME if i else WHITE,'lt',stroke=3);y+=72
        self.egg(im,540,788,95,0)
        self.txt(im,'Egg illustration',540,903,17,'#e1ebe5',stroke=1)
        self.txt(im,'An unexpected journey for a fish egg.',48,1003,29,WHITE,'lt',stroke=2)
        for j,line in enumerate(wrap(self.ep['citation'],19,610,False)):
            self.txt(im,line,48,1093+j*24,19,'#cbdad2','lt',stroke=1)
        self.txt(im,self.ep['doi'],48,1160,20,LIME,'lt',stroke=1)
        return im


def render(ep,voice,out):
    validate_text_layout(ep)
    timeline,captions,audit,duration=voice.make(ep,out)
    bounds=(35,80)
    if not bounds[0]<=duration<=bounds[1]:raise ValueError(f'Film duration outside {bounds}: {duration}')
    if max(s['end']-s['start'] for s in timeline)>7.5:raise ValueError('Shot too long')
    vis=Visuals(ep,out);silent=out/'picture.mp4'
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-vf','scale=1080:1920:flags=lanczos','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',str(silent)]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    for i in range(math.ceil(duration*FPS)):
        t=i/FPS;shot=next((s for s in timeline if s['start']<=t<s['end']),timeline[-1])
        active_caption=next((c for c in captions if c['start']<=t<c['end']),None)
        caption=active_caption['text'] if active_caption else ''
        vis.caption_phase=(t-active_caption['start'])/max(.01,active_caption['end']-active_caption['start']) if active_caption else 1
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
    require_critical_terms(transcript,ep['production']['critical_terms'])
    frames=[]
    for i,s in enumerate(timeline):
        name=f'{ep["id"].lower()}-shot-{i+1:02}.jpg';path=QA/name
        sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str((s['start']+s['end'])/2),'-i',target,'-frames:v','1','-vf','scale=360:640',path])
        with Image.open(path) as im:frames.append(im.copy())
    grid=Image.new('RGB',(1080,640*math.ceil(len(frames)/3)),BG)
    for i,im in enumerate(frames):grid.paste(im,((i%3)*360,(i//3)*640))
    grid.save(QA/(ep['id'].lower()+'-contact.jpg'),quality=91)
    if ep['production'].get('editorial_style')=='science-journalism':
        cover=vis.pilot_cover()
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
        if y<570 and s.get('asset'):
            # Reuse the same licensed decoder for video and image carousel art.
            ref=vis.picture(s['asset'],s.get('offset',4),s.get('focus'))
            art=ImageOps.fit(ref,(616,205))
            canvas.paste(art,(52,575))
        elif y<650 and s.get('visual_kind')=='embryo':
            vis.egg(canvas,360,674,91,0)
            vis.txt(canvas,'Illustration',520,762,17,'#bddcd9')
        elif y<650 and s.get('visual_kind')=='hatchlings':
            for k in range(3):vis.larva(canvas,125+k*205,690,.6,k)
            vis.txt(canvas,'Illustration: after incubation in water',360,760,18,'#bddcd9')
        # No unrequested illustration or recycled result is inserted into a slide.
        d.line((52,803,668,803),fill=TEAL,width=2)
        d.text((52,830),ep['doi'],font=font(22),fill=TEAL)
        canvas.resize((1080,1350),Image.Resampling.LANCZOS).save(MEDIA/f'{ep["slug"]}_slide_{i+1:02}.jpg',quality=95)
    manifest={'renderer':VERSION,'duration':float(info['format']['duration']),'shots':timeline,'captions':captions,'segment_audio':audit,'final_audio_transcript':transcript,'final_script_similarity':similarity,'loudness':loud,'technical_passed':True,'editorial_review_required':True,'listening_review_claimed':False,'contact_sheet':f'qa/{ep["id"].lower()}-contact.jpg','asset_receipts':[{**a,'download_sha256':sha(vis.assets[a['id']])} for a in ep['production']['assets']]}
    manifest['editorial_style']=ep['production'].get('editorial_style','science-journalism')
    manifest['representation']='Reference wildlife footage and labelled original illustrations; no generated research footage.'
    manifest['declared_renderer']=ep['production'].get('renderer','ecology-story-7')
    manifest['voice']={'model':'Kokoro v1.0','voice':'af_heart','speed':float(ep['production'].get('voice_speed',1.00))}
    return manifest
