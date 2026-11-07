"""Toxic Tales v4: reproducible neural narration and shot-based editorial films.

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
VERSION='science-journalism-pilot-6.0'
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
            folder=self.out/('frames-'+key+'-v6-'+p.stem)
            if key not in self.frames:
                folder.mkdir(exist_ok=True)
                sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',p,'-t','18','-vf','fps=24,scale=-2:1280:flags=lanczos',folder/'%05d.jpg'])
                self.frames[key]=sorted(folder.glob('*.jpg'))
            fs=self.frames[key];p=fs[int(t*24)%len(fs)]
        with Image.open(p) as original:src=original.convert('RGB')
        if wide:
            im=ImageOps.fit(src,(W,H)).filter(ImageFilter.GaussianBlur(22));im=Image.blend(im,Image.new('RGB',(W,H),BG),.65)
            fg=ImageOps.contain(src,(W,650));im.paste(fg,((W-fg.width)//2,290+(650-fg.height)//2))
        else:im=ImageOps.fit(src,(W,H),centering=(.5,.5))
        return im
    def story_frame(self,shot,t,caption='',progress=0):
        """Full-frame reference footage, kinetic captions and explanatory animation."""
        typ=shot['kind'];local=t-shot['start'];phase=max(0,min(1,local/max(.01,shot['end']-shot['start'])))
        ease=1-(1-min(1,local/.45))**3
        live=typ in ('nature','micro','landscape')
        if live and shot.get('asset'):
            im=self.picture(shot['asset'],local+shot.get('offset',0))
        elif typ=='specimen' and shot.get('asset'):
            # Landscape specimen remains whole; its black background meets the canvas.
            im=Image.new('RGB',(W,H),'#020605')
            with Image.open(self.assets[shot['asset']]) as source:
                fg=ImageOps.contain(source.convert('RGB'),(int(690+18*math.sin(local*.35)),540))
            im.paste(fg,((W-fg.width)//2,550-fg.height//2))
        else:
            if not hasattr(self,'backplate'):
                yy,xx=np.mgrid[0:H,0:W];glow=np.exp(-(((xx-W*.55)/(W*.64))**2+((yy-H*.47)/(H*.37))**2)*2.5)
                arr=np.zeros((H,W,3),dtype=np.uint8)
                for k,(base,light) in enumerate(((2,5),(6,19),(5,17))):arr[:,:,k]=base+glow*light
                self.backplate=Image.fromarray(arr)
            im=self.backplate.copy()
        overlay=Image.new('RGBA',(W,H));od=ImageDraw.Draw(overlay)
        for y in range(H):
            alpha=int(145*max(0,1-y/330)+170*max(0,(y-860)/420)) if live else 0
            if alpha:od.line((0,y,W,y),fill=(0,4,3,alpha))
        im=Image.alpha_composite(im.convert('RGBA'),overlay).convert('RGB');d=ImageDraw.Draw(im)
        white='#ffffff';lime='#c9ff36';cyan='#67e4da';coral='#ff997b'
        # Restrained texture gives drawings movement without implying data.
        if not live and typ!='specimen':
            for k in range(22):
                xx=(k*107+math.sin(k*2.1+local*.24)*20)%W
                yy=250+(k*163-local*(7+k%4))%610
                r=1+k%2
                d.ellipse((xx-r,yy-r,xx+r,yy+r),fill='#254335')

        def text(txt,x,y,size=32,color=white,anchor='mm',italic=False):
            d.text((x,y),txt,font=font(size,italic=italic),fill=color,anchor=anchor,
                   stroke_width=1 if live else 0,stroke_fill='#020604')
        def headline(txt,y=190,size=58,color=white,width=620):
            lines=wrap(txt,size,width)
            for k,line in enumerate(lines):
                text(line,52,y+k*(size+5),size,color,'lt')
            return y+len(lines)*(size+5)
        def small(txt,y=852,color='#c0d2cc'):
            text(txt,360,y,19,color)
        def arrow(a,b,color=cyan):
            x1,y1=a;x2,y2=b
            d.line((x1,y1,x2,y2),fill=color,width=5)
            ang=math.atan2(y2-y1,x2-x1)
            d.polygon([(x2,y2),(x2-16*math.cos(ang-.55),y2-16*math.sin(ang-.55)),
                       (x2-16*math.cos(ang+.55),y2-16*math.sin(ang+.55))],fill=color)
            q=(local*.32)%1;xx=x1+(x2-x1)*q;yy=y1+(y2-y1)*q
            d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=white)
        def algae(cx,cy,s=1):
            for k in range(8):
                a=k*2.399+local*.15;r=(10+9*math.sqrt(k))*s
                xx=cx+r*math.cos(a);yy=cy+r*.65*math.sin(a)
                d.ellipse((xx-10*s,yy-15*s,xx+10*s,yy+15*s),fill='#315c27',outline=lime,width=2)
                d.line((xx,yy-9*s,xx,yy+9*s),fill='#88ad49',width=1)
        def plankter(cx,cy,s=1,color=cyan):
            cy+=math.sin(local*1.8)*7
            # Copepod-inspired schematic; never presented as a measured animal.
            pts=[(cx,cy-77*s),(cx+33*s,cy-51*s),(cx+39*s,cy-14*s),
                 (cx+24*s,cy+33*s),(cx+12*s,cy+70*s),(cx-12*s,cy+70*s),
                 (cx-24*s,cy+33*s),(cx-39*s,cy-14*s),(cx-33*s,cy-51*s)]
            d.polygon(pts,fill='#103f3d',outline=color,width=3)
            for j in range(4):
                yy=cy+(10+j*15)*s;hw=(24-j*4)*s
                d.line((cx-hw,yy,cx+hw,yy),fill=color,width=2)
            d.ellipse((cx-5*s,cy-51*s,cx+5*s,cy-41*s),fill=coral)
            for side in (-1,1):
                sway=math.sin(local*3)*8
                d.line((cx+side*17*s,cy-52*s,cx+side*73*s,cy-99*s,
                        cx+side*(112+sway)*s,cy-91*s),fill=color,width=3)
                for j in range(3):
                    yy=cy+(-20+j*19)*s
                    d.line((cx+side*32*s,yy,cx+side*59*s,yy+22*s,
                            cx+side*(79+math.sin(local*4+j)*7)*s,yy+15*s),fill=color,width=2)
                d.line((cx+side*8*s,cy+70*s,cx+side*20*s,cy+100*s,
                        cx+side*39*s,cy+112*s),fill=color,width=2)
        def predator(cx,cy,s=1,color=cyan):
            # The mosquitofish photograph carries the taxonomic identification.
            fish(d,cx,cy,s,color)
            d.polygon([(cx-6*s,cy-12*s),(cx-20*s,cy-29*s),(cx+10*s,cy-12*s)],fill='#2d7466')
            d.polygon([(cx-5*s,cy+11*s),(cx-19*s,cy+26*s),(cx+11*s,cy+10*s)],fill='#2d7466')
            d.arc((cx+8*s,cy-10*s,cx+21*s,cy+12*s),90,255,fill='#193a34',width=2)
        def residues(cx=360,cy=545):
            for k in range(9):
                a=k*2.399+local*.32;r=150+25*math.sin(k)
                xx=cx+r*math.cos(a);yy=cy+r*.77*math.sin(a)
                d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=coral)

        text('TOXIC TALES',50,82,20,lime,'lt')
        # Section labels stay secondary to the footage, not a duplicate subtitle.
        if shot.get('kicker') and typ not in ('specimen','micro'):
            text(shot['kicker'].upper(),50,117,16,'#a8c0b5','lt')
        if typ=='specimen':
            if shot.get('segment',0)==0:
                headline('FISH GONE.',180,73,lime)
                headline('WHAT NOW?',267,62)
                # Motion cue follows the real specimen without masking its eye.
                d.line((65,760,65+int(500*ease),760),fill=lime,width=4)
                small('A recovery story with a second pressure',810)
            else:
                headline('THE PREDATOR',190,51,lime)
                text('Eastern mosquitofish',360,752,34)
        elif typ=='foodweb':
            headline('SMALL ANIMALS. BIG CONNECTIONS.',173,49)
            predator(220+math.sin(local)*9,393,2.1);text('FISH',480,393,34)
            plankter(220,601,.93);text('ZOOPLANKTON',470,595,28,lime)
            algae(220,806,1.1);text('ALGAE',480,802,34)
            arrow((220,749),(220,700),lime);arrow((220,480),(220,442),cyan)
            text('food',286,726,18,'#91bba7');text('food',286,463,18,'#91bba7')
        elif typ=='wastewater_route':
            headline('ANOTHER PRESSURE ENTERS THE WATER.',177,49)
            # The route crosses one continuous landscape, rather than a stack of cards.
            d.polygon([(70,470),(70,404),(116,370),(161,404),(161,470)],fill='#14352c',outline=cyan,width=3)
            d.rectangle((105,433,124,470),fill=cyan);text('Homes',119,505,24)
            d.line((161,450,235,450,235,553,330,553),fill='#456b59',width=14)
            d.rectangle((330,485,554,619),fill='#15392f',outline=cyan,width=3)
            for j in range(3):
                yy=510+j*36;d.line((350,yy,531,yy),fill='#528d73',width=3)
            text('Treatment',442,655,28)
            d.line((554,562,632,562,632,728),fill='#456b59',width=13)
            for j in range(5):
                pts=[(25+k*9,755+j*22+6*math.sin(k*.28+local+j)) for k in range(76)]
                d.line(pts,fill=cyan if j%2==0 else '#2b6958',width=3)
            # A few symbolic residues; their number has no quantitative meaning.
            for j in range(3):
                q=(local*.28+j*.3)%1
                xx=632 if q<.5 else 632-(q-.5)*700;yy=640+q*190 if q<.5 else 754+10*math.sin(q*9+j)
                d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=coral)
            text('Some residues remain',360,887,24,coral)
        elif typ=='restoration_question':
            next_y=headline('ONE PRESSURE ENDS.',180,48,lime)
            headline('ANOTHER STAYS.',next_y+10,48)
            predator(430-800*min(1,phase*1.4),439,3.2)
            if phase>.34:
                d.line((76,437,187,437),fill='#3d6854',width=3)
                text('fish removed',470,420,26,cyan)
            plankter(360,652,1.42);residues(360,635)
            text(shot.get('pressure_label','Continuing exposure'),360,853,31,coral)
        elif typ=='evidence_rebound':
            headline('THE REBOUND WAS SMALLER.',179,57)
            # Equal-sized organism symbols deliberately avoid implying effect sizes.
            plankter(155,500,.80,cyan);text('No fluoxetine',465,458,28,cyan)
            text('Stronger',465,514,40);text('rebound',465,560,40)
            plankter(155,749,.80,coral);text('Exposure continued',465,709,25,coral)
            text('Smaller',465,760,40);text('rebound',465,806,40)
        elif typ=='tanks':
            headline('A SMALL WORLD, BUILT OUTDOORS.',175,51)
            for col,(name,color) in enumerate([('CONTROL',cyan),('LOW',lime),('HIGHER',coral)]):
                x=133+col*224;text(name,x,364,23,color)
                for row in range(4):
                    yy=444+row*99
                    d.rounded_rectangle((x-77,yy-19,x+77,yy+34),10,fill='#15362e',outline=color,width=2)
                    d.ellipse((x-77,yy-31,x+77,yy+12),fill='#1d483f',outline=color,width=2)
                    d.arc((x-60,yy-23,x+60,yy+5),0,180,fill='#507264',width=2)
                    predator(x+math.sin(local*1.4+row+col)*17,yy-7,.48,color)
            text('12 tanks',360,870,42,lime)
        elif typ=='timeline':
            headline('THEN CAME FLUOXETINE.',175,51)
            items=[('01','FISH INTRODUCED',cyan),('02','DRUG ADDED',coral),('03','FISH REMOVED',cyan)]
            for j,(num,txt,color) in enumerate(items):
                yy=400+j*174
                text(num,87,yy,47,color)
                text(txt,160,yy,29,white,'lm')
                if j<2:d.line((87,yy+47,87,yy+119),fill='#365344',width=3)
            d.line((642,571,642,803),fill=coral,width=7)
            text('Dosing continues',455,867,26,coral)
        elif typ=='micro':
            seg=shot.get('segment',-1)
            # High-resolution portrait microscopy fills the frame. It is reference footage.
            if seg==0:headline('WHAT IF SOMETHING ELSE STAYS?',177,49)
            elif seg==1:headline('MEET THE ZOOPLANKTON.',177,49,lime)
            elif seg==2:headline('A SECOND PRESSURE',177,49)
            elif seg==7:headline('THE DRUG KEPT COMING.',177,53,coral)
            elif seg==8:headline('THE “WHY” IS STILL OPEN.',177,50)
            elif seg==9:headline('DRUG REMOVAL WAS NOT TESTED.',177,49,coral)
            elif seg==11:headline('WHAT ELSE IS HOLDING RECOVERY BACK?',177,47,lime)
        elif typ in ('nature','landscape'):
            scene_title='A ROUTE INTO FRESH WATER.' if seg==2 else 'FROM TANKS TO THE WIDER WORLD.'
            headline(shot.get('title',scene_title),177,48)
        elif typ=='limit':
            headline('WHAT THE STUDY CANNOT TELL US.',175,49)
            for j,item in enumerate(shot['items']):
                yy=435+j*145
                d.line((52,yy,52,yy+70),fill=coral,width=4)
                for k,line in enumerate(wrap(item,32,560)):text(line,78,yy+k*41,32,white,'lt')
        elif typ=='story_close':
            headline('WHAT ELSE IS HOLDING RECOVERY BACK?',183,57,lime)
            predator(560+math.sin(local)*13,505,1.8)
            plankter(350,631,1.05);algae(144,755,1.1)
            arrow((197,733),(277,676),lime);arrow((422,574),(498,527),cyan)
            residues(350,631)
            text('One pressure removed. Others may remain.',360,845,23)
        else:raise ValueError('Unsupported journalism scene: '+typ)

        # Bold outlined captions occupy the visual field like the owner's VEED references.
        if caption:
            lines=wrap(caption,46,610)
            if len(lines)>3:raise ValueError('Pilot caption exceeds 3 lines: '+caption)
            cp=getattr(self,'caption_phase',.5)
            bounce=int(9*(1-min(1,cp*8))**2)
            cy=1005-(len(lines)-1)*28+bounce
            layer=Image.new('RGBA',(W,H));ld=ImageDraw.Draw(layer)
            for yy in range(cy-45,min(H,cy+len(lines)*58+55)):
                fade=max(0,1-abs(yy-(cy+len(lines)*27))/(len(lines)*30+65))
                ld.line((0,yy,W,yy),fill=(0,4,2,int(92*fade)))
            im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB');d=ImageDraw.Draw(im)
            for j,line in enumerate(lines):
                # Phrase emphasis is typographic, not claimed word-level forced alignment.
                color=lime if j==len(lines)-1 and any(w in line.lower() for w in ('pressure','recover','rebound','removed','remained','zooplankton')) else white
                d.text((354,cy+j*58),line,font=font(46,italic=True),fill=color,
                       anchor='mt',stroke_width=3,stroke_fill='#010603')
        if shot.get('note'):
            note=shot['note'].replace('•',' / ')
            for j,line in enumerate(wrap(note,18,620,False)):
                d.text((50,1155+j*23),line,font=font(18,False),fill='#edf4ef',stroke_width=1,stroke_fill='#020604')
        d.rectangle((50,1230,50+int(620*progress),1233),fill=lime)
        return im

    def pilot_cover(self):
        # The cover is designed as a standalone poster at native composition size.
        im=self.picture(self.ep['production']['cover_asset'],t=7)
        mask=Image.new('RGBA',(W,H));d=ImageDraw.Draw(mask)
        for y in range(H):
            alpha=int(210*max(0,1-y/600)+230*max(0,(y-745)/535))
            d.line((0,y,W,y),fill=(0,5,3,min(240,alpha)))
        im=Image.alpha_composite(im.convert('RGBA'),mask).convert('RGB');d=ImageDraw.Draw(im)
        d.text((50,91),'TOXIC TALES',font=font(24),fill='#c9ff36')
        for j,(txt,col) in enumerate([('FISH GONE.', '#ffffff'),('POLLUTION', '#c9ff36'),('STAYS.', '#c9ff36')]):
            d.text((48,190+j*80),txt,font=font(65),fill=col,stroke_width=3,stroke_fill='#020604')
        label(im,'Why recovery is not always a clean reset.',935,34,width=605,center=False,stroke=2)
        label(im,self.ep['citation'],1085,19,'#d2ddd5',width=615,center=False)
        label(im,self.ep['doi'],1130,21,'#c9ff36',width=615,center=False)
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
