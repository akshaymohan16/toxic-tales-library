"""Native-HD nature stories: real photographs and source-specific explanatory motion.

Isolated from all frozen published renderers. Every photograph is reference imagery;
the animated cell diagrams are conceptual, not microscopy or simulated study data.
"""
import difflib, hashlib, json, math, subprocess
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from production_pilot import Voice, download, sh, sha, norm, require_critical_terms

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'site/media'; QA=ROOT/'site/qa'; CACHE=ROOT/'render-cache'
W,H,FPS=1080,1920,24
VERSION='nature-story-8.0'
BG='#071c22'; INK='#09262c'; PAPER='#f5f2e7'; ICE='#a9e7ee'
MINT='#c4e5a3'; AMBER='#f4b969'; MUTED='#a8c2c3'; BLUE='#51a9c0'
FONT_SPECS=[
 {'id':'sans','family':'Manrope','url':'https://raw.githubusercontent.com/google/fonts/4024282d9b0cffcdb8e3024560862746178d741f/ofl/manrope/Manrope%5Bwght%5D.ttf','filename':'4024282-Manrope-wght.ttf','license':'SIL Open Font License 1.1','license_url':'https://raw.githubusercontent.com/google/fonts/4024282d9b0cffcdb8e3024560862746178d741f/ofl/manrope/OFL.txt'},
 {'id':'display','family':'Fraunces','url':'https://raw.githubusercontent.com/google/fonts/4024282d9b0cffcdb8e3024560862746178d741f/ofl/fraunces/Fraunces%5BSOFT%2CWONK%2Copsz%2Cwght%5D.ttf','filename':'4024282-Fraunces-variable.ttf','license':'SIL Open Font License 1.1','license_url':'https://raw.githubusercontent.com/google/fonts/4024282d9b0cffcdb8e3024560862746178d741f/ofl/fraunces/OFL.txt'}]

def clamp(x): return max(0,min(1,x))
def ease(x): x=clamp(x); return x*x*(3-2*x)
def rgba(c,a=255): return tuple(int(c[i:i+2],16) for i in (1,3,5))+(int(a),)

class Typography:
    def __init__(self,preview=False):
        self.paths={};self.receipts=[]
        for spec in FONT_SPECS:
            if preview:
                self.paths[spec['id']]=Path('C:/Windows/Fonts/georgia.ttf' if spec['id']=='display' else 'C:/Windows/Fonts/bahnschrift.ttf')
            else:
                path=download(spec['url'],CACHE/'fonts'/spec['filename'])
                license_path=download(spec['license_url'],CACHE/'fonts'/(spec['family']+'-4024282-OFL.txt'))
                public_license=ROOT/'site/licenses'/(spec['family']+'-OFL.txt')
                public_license.parent.mkdir(parents=True,exist_ok=True)
                public_license.write_bytes(license_path.read_bytes())
                self.paths[spec['id']]=path
                self.receipts.append({**spec,'download_sha256':sha(path),'license_sha256':sha(license_path),'archived_license':'licenses/'+public_license.name,'upstream_commit':'4024282d9b0cffcdb8e3024560862746178d741f'})
        self.preview=preview

    @lru_cache(maxsize=96)
    def font(self,size,face='sans',weight=600):
        f=ImageFont.truetype(str(self.paths[face]),int(size))
        if not self.preview:
            axes=f.get_variation_axes()
            values=[]
            for a in axes:
                name=a['name'].decode() if isinstance(a['name'],bytes) else str(a['name'])
                v=weight if 'weight' in name.lower() else 60 if 'optical' in name.lower() else a['default']
                values.append(max(a['minimum'],min(a['maximum'],v)))
            if values:f.set_variation_by_axes(values)
        return f

    def wrap(self,text,size,width,face='sans',weight=600):
        d=ImageDraw.Draw(Image.new('RGB',(1,1)));result=[]
        for paragraph in text.split('\n'):
            line=''
            for word in paragraph.split():
                trial=(line+' '+word).strip()
                if d.textlength(trial,font=self.font(size,face,weight))>width and line:
                    result.append(line);line=word
                else:line=trial
            if line:result.append(line)
        return result

    def block(self,im,text,x,y,size=52,color=PAPER,width=900,face='sans',weight=600,leading=1.17,anchor='lt',max_lines=None):
        lines=self.wrap(text,size,width,face,weight)
        if max_lines and len(lines)>max_lines:raise ValueError('Text exceeds layout: '+text)
        d=ImageDraw.Draw(im)
        for i,line in enumerate(lines):d.text((x,y+i*size*leading),line,font=self.font(size,face,weight),fill=color,anchor=anchor)
        return y+len(lines)*size*leading

    def text(self,im,text,x,y,size=32,color=PAPER,face='sans',weight=600,anchor='lt'):
        ImageDraw.Draw(im).text((x,y),text,font=self.font(size,face,weight),fill=color,anchor=anchor)

class Visuals:
    def __init__(self,ep,out,preview=False):
        self.ep=ep;self.out=Path(out);self.preview=preview;self.type=Typography(preview)
        self.assets={};self.photos={};self.info={}
        for a in ep['production']['assets']:
            self.info[a['id']]=a
            if preview and not a.get('local_preview_path'):continue
            if a.get('local_preview_path') and preview:p=Path(a['local_preview_path'])
            else:p=download(a['url'],CACHE/'assets'/(hashlib.sha256(a['url'].encode()).hexdigest()[:12]+'-'+a['filename']),a.get('sha256'))
            self.assets[a['id']]=p
            with Image.open(p) as im:self.photos[a['id']]=im.convert('RGB')
        yy,xx=np.mgrid[0:H,0:W]
        glow=np.exp(-(((xx-W*.54)/(W*.8))**2+((yy-H*.4)/(H*.55))**2)*3)
        a=np.zeros((H,W,3),dtype=np.uint8)
        for k,(base,light) in enumerate(((5,9),(21,30),(27,34))):a[:,:,k]=base+glow*light
        self.background=Image.fromarray(a)
        self.vignette=Image.new('RGBA',(W,H));d=ImageDraw.Draw(self.vignette)
        for y in range(H):
            alpha=200*max(0,1-y/740)+235*max(0,(y-1120)/800)
            if alpha:d.line((0,y,W,y),fill=(0,12,15,min(240,int(alpha))))

    def photograph(self,key,t=0,focus=None,size=(W,H)):
        if key not in self.photos:
            if not self.preview:raise ValueError('Missing required licensed photograph: '+str(key))
            im=ImageOps.fit(self.background,size)
            self.type.text(im,'PHOTO COMPOSITION PLACEHOLDER',size[0]/2,size[1]/2,28,MUTED,anchor='mm')
            return im
        src=self.photos[key];cx,cy=focus or self.info[key].get('focus',[.5,.5])
        zoom=1.015+.025*math.sin(t*.13)
        crop=ImageOps.fit(src,(int(size[0]*zoom),int(size[1]*zoom)),Image.Resampling.LANCZOS,centering=(cx,cy))
        # This movement is an editorial camera crop of a still photograph.
        return ImageOps.fit(crop,size,Image.Resampling.LANCZOS)

    def gradient_photo(self,key,t=0,focus=None):
        im=self.photograph(key,t,focus).convert('RGBA')
        return Image.alpha_composite(im,self.vignette).convert('RGB')

    def crystal(self,im,x,y,r,phase=1,color=ICE):
        d=ImageDraw.Draw(im);r*=ease(phase)
        for j in range(6):
            a=j*math.pi/3;ex=x+r*math.cos(a);ey=y+r*math.sin(a)
            d.line((x,y,ex,ey),fill=color,width=3)
            for f in (.45,.72):
                bx=x+r*f*math.cos(a);by=y+r*f*math.sin(a)
                for side in (-1,1):
                    angle=a+side*math.pi/3
                    d.line((bx,by,bx-r*.19*math.cos(angle),by-r*.19*math.sin(angle)),fill=color,width=2)

    def cell(self,im,cx,cy,r,t=0,protected=True,ice=True,phase=1,labels=True):
        layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer)
        pts=[]
        for i in range(121):
            a=i/120*math.tau;rr=r*(1+.018*math.sin(a*5+t*.6)+.014*math.sin(a*8))
            pts.append((cx+rr*math.cos(a),cy+rr*.92*math.sin(a)))
        d.polygon(pts,fill=(23,77,82,205));d.line(pts,fill=rgba(ICE,200),width=5)
        pts2=[(cx+(x-cx)*.962,cy+(y-cy)*.962) for x,y in pts]
        d.line(pts2,fill=(105,187,182,70),width=3)
        d.ellipse((cx-r*.27,cy-r*.22,cx+r*.18,cy+r*.2),fill=(13,46,62,180),outline=(121,179,188,100),width=3)
        # Molecule positions are diagrammatic, never a measured number/concentration.
        rng=np.random.default_rng(5107);points=[]
        while len(points)<34:
            nx,ny=rng.uniform(-.8,.8,2)
            if nx*nx+(ny/.92)**2>.8**2:continue
            if ((nx+.045)/.33)**2+((ny+.01)/.29)**2<1:continue
            if any((nx-px)**2+(ny-py)**2<.12**2 for px,py in points):continue
            points.append((nx,ny))
        for i,(nx,ny) in enumerate(points):
            x=cx+r*(nx+.012*math.sin(t*.42+i*1.7))
            y=cy+r*(ny+.012*math.cos(t*.37+i*2.3))
            rad=6 if protected else 4;col=AMBER if protected else '#8ccbd8'
            d.ellipse((x-rad,y-rad,x+rad,y+rad),fill=rgba(col,210))
        glow=layer.filter(ImageFilter.GaussianBlur(11))
        im.paste(Image.alpha_composite(Image.alpha_composite(im.convert('RGBA'),glow),layer).convert('RGB'))
        if ice:
            for j in range(8):
                a=j*math.tau/8+.12;rr=r+68+(j%2)*28
                self.crystal(im,cx+rr*math.cos(a),cy+rr*.92*math.sin(a),27+j%3*6,clamp(phase*1.8-j*.11),ICE)
        if labels:
            self.type.text(im,'ICE OUTSIDE CELLS',cx,cy-r-155,29,ICE,weight=700,anchor='mt')
            self.type.text(im,'Cell membrane',cx,cy+r+115,27,MUTED,weight=500,anchor='mt')
            if protected:
                d=ImageDraw.Draw(im);d.ellipse((cx-176,cy+r+182,cx-162,cy+r+196),fill=AMBER)
                self.type.text(im,'Protective solutes',cx-142,cy+r+175,29,AMBER,weight=600)

    def solutes(self,im,t=0,p=1):
        # Two explicit timing cues rather than an invented quantitative mechanism.
        y0=610;d=ImageDraw.Draw(im)
        self.type.text(im,'BEFORE FREEZING',82,y0,26,ICE,weight=700)
        self.type.text(im,'Urea builds up',82,y0+50,56,PAPER,face='display')
        self.type.text(im,'AS FREEZING BEGINS',82,y0+195,26,AMBER,weight=700)
        self.type.text(im,'Liver stores become glucose',82,y0+245,48,PAPER,face='display')
        for j in range(7):
            x=100+j*54;y=y0+364+math.sin(j*.8)*17
            d.ellipse((x-11,y-11,x+11,y+11),fill=AMBER)
            if j:d.line((x-43,y0+364+math.sin((j-1)*.8)*17,x-12,y),fill=AMBER,width=3)
        for j in range(6):
            q=(t*.22+j/6)%1;x=480+q*235;y=y0+364+32*math.sin(q*math.pi)
            d.ellipse((x-8,y-8,x+8,y+8),fill=AMBER)
        self.cell(im,836,y0+366,142,t,True,False,labels=False)
        self.type.text(im,'Conceptual pathway • not molecular counts',82,y0+565,25,MUTED,weight=500)

    def water_outflow(self,im,cx,cy,r,t=0,small=False):
        # Extracellular ice draws some water out. The route and markers explain
        # direction only: they are not a measured flux, volume or molecule count.
        layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer)
        a=-math.pi*.18;ux,uy=math.cos(a),math.sin(a)
        start=.68*r;end=1.44*r
        x1,y1=cx+start*ux,cy+start*uy
        x2,y2=cx+end*ux,cy+end*uy
        d.line((x1,y1,x2,y2),fill=rgba(BLUE,130),width=3)
        for sign in (-1,1):
            aa=a+math.pi+sign*.45
            d.line((x2,y2,x2+18*math.cos(aa),y2+18*math.sin(aa)),fill=rgba(BLUE,210),width=3)
        for j in range(3):
            q=(t*.25+j/3)%1;rr=start+(end-start)*q
            x,y=cx+rr*ux,cy+rr*uy;rad=6 if small else 8
            alpha=int(220*min(1,q*8,(1-q)*8))
            d.ellipse((x-rad,y-rad,x+rad,y+rad),fill=rgba(ICE,alpha))
        im.paste(Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB'))
        self.type.text(im,'Water moves out',cx+r*.90,cy-r*1.12,23 if small else 27,ICE,weight=500,anchor='mm')

    def trial(self,im,t=0,p=1,recovery=False):
        d=ImageDraw.Draw(im)
        if not recovery:
            self.type.text(im,'CONTROLLED FREEZE / THAW',82,585,27,ICE,weight=700)
            for j in range(3):
                cx=202+j*325;cy=790
                d.arc((cx-84,cy-84,cx+84,cy+84),35,325,fill=ICE,width=4)
                a=(t*.5+j)*math.tau
                dotx=cx+84*math.cos(a);doty=cy+84*math.sin(a)
                d.ellipse((dotx-7,doty-7,dotx+7,doty+7),fill=MINT)
                self.crystal(im,cx,cy,37,1)
                self.type.text(im,str(j+1),cx,cy+124,32,MUTED,anchor='mm')
            self.type.text(im,'Repeated cycles',540,1000,36,PAPER,anchor='mm')
            self.type.text(im,'Final freeze',540,1116,28,MUTED,anchor='mm')
            self.type.text(im,'−8°C',540,1220,114,ICE,face='display',anchor='mm')
        else:
            self.type.text(im,'SURVIVAL FOLLOW-UP',82,582,27,MINT,weight=700)
            for i in range(5):
                x=174+i*181;cy=800;arrive=clamp(p*2-i*.14)
                d.ellipse((x-58,cy-58,x+58,cy+58),fill='#173d3d',outline=MINT,width=3)
                if arrive>.2:d.line([(x-22,cy),(x-5,cy+19),(x+28,cy-21)],fill=MINT,width=5)
            self.type.text(im,'5 of 5',540,1000,104,PAPER,face='display',anchor='mm')
            self.type.text(im,'recovered',540,1110,47,MINT,face='display',anchor='mm')
            self.type.text(im,'Healthy through 7 weeks of follow-up',540,1220,31,MUTED,weight=500,anchor='mm')

    def woodland(self,im,t=0,p=1):
        """A general woodland-floor concept, not a mapped site or measured winter."""
        layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer)
        for j,x in enumerate((20,180,370,720,915,1080)):
            base=1170;top=460+(j%3)*90;width=13+(j%2)*9
            d.line((x,base,x+20*math.sin(j),top),fill=(27,62,64,150),width=width)
            for k in range(4):
                y=top+100+k*105;side=-1 if k%2 else 1
                d.line((x,y+45,x+side*(55+k*13),y-55),fill=(34,73,73,150),width=max(3,width//3))
        d.polygon([(0,1180),(240,1150),(520,1185),(800,1145),(1080,1175),(1080,1390),(0,1390)],fill=(35,62,49,240))
        for j in range(45):
            x=25+(j*137)%1040;y=1170+(j*43)%165
            angle=(j*1.73)%math.tau;length=22+(j%4)*8
            points=[]
            for q in range(41):
                a=q/40*math.tau;xx=math.cos(a)*length;yy=math.sin(a)*length*.38
                points.append((x+xx*math.cos(angle)-yy*math.sin(angle),y+xx*math.sin(angle)+yy*math.cos(angle)))
            d.polygon(points,fill=rgba(('#77633f','#9c8050','#5d7050','#aa8b5a')[j%4],210))
            d.line((x-length*.7*math.cos(angle),y-length*.7*math.sin(angle),x+length*.7*math.cos(angle),y+length*.7*math.sin(angle)),fill=(194,171,107,100),width=1)
        # A few leaves settling locates the seasonal preparation in a forest floor.
        for j in range(3):
            q=(t*.075+j*.32)%1;x=240+j*270+38*math.sin(q*math.tau);y=550+q*620
            d.ellipse((x-13,y-23,x+13,y+23),fill=(182,143,73,180))
        im.paste(Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB'))
        self.type.text(im,'INTERIOR ALASKA',540,670,34,ICE,weight=700,anchor='mm')
        self.type.block(im,'Preparation starts\nbefore the first freeze.',540,760,55,PAPER,width=830,face='display',anchor='mt',max_lines=2)
        self.type.text(im,'Woodland floor • conceptual setting',540,1370,25,MUTED,weight=500,anchor='mm')

    def diagram(self,kind,t,p,shot=None):
        im=self.background.copy();shot=shot or {}
        if kind=='winter':self.woodland(im,t,p)
        elif kind=='cells':
            self.cell(im,540,910,250,t,protected=True,ice=True,phase=.25+.75*p)
            self.water_outflow(im,540,910,250,t)
        elif kind=='glucose':self.solutes(im,t,p)
        elif kind=='experiment':self.trial(im,t,p)
        elif kind=='recovery':self.trial(im,t,p,True)
        elif kind=='scope':
            self.type.text(im,'THE BOUNDARY',82,620,28,AMBER,weight=700)
            self.type.block(im,'Five frogs.\nOne controlled study.',82,690,76,PAPER,face='display',max_lines=3)
            self.type.block(im,'Winter-conditioned animals\nfrom interior Alaska.',82,965,40,MUTED,weight=500,max_lines=3)
            self.type.block(im,'Other populations can differ.',82,1160,40,ICE,weight=600,max_lines=2)
        else:raise ValueError('Unrecognized nature diagram: '+kind)
        return im

    def frame(self,shot,t,caption='',progress=0):
        local=max(0,t-shot['start']);duration=max(.01,shot['end']-shot['start']);p=clamp(local/duration)
        kind=shot['kind'];photo=kind in ('portrait','closing','nature') or (kind=='winter' and bool(shot.get('asset')))
        im=self.gradient_photo(shot['asset'],local+shot.get('offset',0),shot.get('focus')) if photo else self.diagram(kind,local,p,shot)
        if photo and shot.get('inset_cell'):
            layer=Image.new('RGBA',(W,H));ld=ImageDraw.Draw(layer)
            ld.ellipse((704,958,1036,1290),fill=(4,24,31,225),outline=(160,210,211,110),width=2)
            im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
            self.cell(im,870,1124,102,local,True,True,1,False)
            self.type.text(im,'Cell illustration',870,1330,22,MUTED,weight=500,anchor='mm')
        d=ImageDraw.Draw(im)
        self.type.text(im,'TOXIC TALES',82,88,25,MINT,weight=750)
        self.type.text(im,'FIELD NOTES  /  '+self.ep['id'].split('-')[-1],82,133,21,MUTED,weight=500)
        kicker=shot.get('kicker','WOOD FROG' if photo else 'INSIDE THE SURVIVAL STRATEGY')
        self.type.text(im,kicker.upper(),82,240,26,ICE,weight=700)
        title=shot.get('title','')
        self.type.block(im,title,78,295,shot.get('title_size',82),PAPER,width=910,face='display',weight=600,leading=1.06,max_lines=3)
        if shot.get('subtitle'):self.type.block(im,shot['subtitle'],82,shot.get('subtitle_y',490),33,MUTED,width=900,weight=500,max_lines=2)
        if caption:
            lines=self.type.wrap(caption,59,874,'sans',650)
            if len(lines)>2:raise ValueError('Caption needs shorter phrase: '+caption)
            top=1510-(len(lines)-1)*33
            layer=Image.new('RGBA',(W,H));ld=ImageDraw.Draw(layer)
            ld.rounded_rectangle((66,top-27,1014,top+len(lines)*75+25),radius=24,fill=(3,17,22,220))
            im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
            for j,line in enumerate(lines):self.type.text(im,line,540,top+j*75,59,PAPER,weight=650,anchor='mt')
        default='Reference photograph • not the study animals' if photo else 'Conceptual animation • not to scale'
        note=shot.get('note',default)
        self.type.block(im,note,82,1748,24,MUTED,width=900,weight=500,leading=1.2,max_lines=2)
        d=ImageDraw.Draw(im);d.line((82,1832,998,1832),fill='#254047',width=2)
        d.line((82,1832,82+916*clamp(progress),1832),fill=MINT,width=3)
        return im

    def cover(self):
        plan=self.ep['production'];im=self.gradient_photo(plan['cover_asset'],0,plan.get('cover_focus'))
        self.type.text(im,'TOXIC TALES',82,100,28,MINT,weight=750)
        self.type.text(im,'THE WOOD FROG',82,270,27,ICE,weight=750)
        title=plan.get('cover_title','Ice inside.\nStill alive.')
        self.type.block(im,title,74,335,112,PAPER,width=920,face='display',weight=600,leading=1.02,max_lines=4)
        self.type.block(im,'How its cells survive the freeze',82,1490,46,PAPER,width=880,weight=600,max_lines=2)
        self.type.text(im,'RESEARCH BEHIND THE STORY',82,1675,25,MINT,weight=700)
        self.type.text(im,'Costanzo et al. · PLOS ONE · 2015',82,1727,27,MUTED,weight=500)
        self.type.text(im,'Reference photograph',82,1816,22,MUTED,weight=500)
        return im

    def slide(self,s,i,n):
        kind=s.get('visual_kind',('portrait','cells','glucose','experiment','recovery','scope')[min(i,5)])
        if kind=='portrait':
            key=s.get('asset',self.ep['production']['cover_asset'])
            pic=self.photograph(key,0,s.get('focus'),(1080,1350)).convert('RGBA')
            canvas=Image.alpha_composite(pic,self.vignette.resize((1080,1350),Image.Resampling.LANCZOS)).convert('RGB')
        else:canvas=ImageOps.fit(self.background,(1080,1350))
        d=ImageDraw.Draw(canvas)
        self.type.text(canvas,'TOXIC TALES',72,65,25,MINT,weight=750)
        self.type.text(canvas,f'{i+1:02} / {n:02}',1008,65,25,MUTED,weight=600,anchor='rt')
        self.type.block(canvas,s['headline'],68,145,76,PAPER,width=945,face='display',weight=600,leading=1.07,max_lines=3)
        self.type.block(canvas,s['body'],72,420,36,PAPER if kind=='portrait' else MUTED,width=930,weight=500,leading=1.22,max_lines=4)
        if kind=='portrait':
            self.type.text(canvas,'Reference photograph',1008,1180,22,PAPER,weight=500,anchor='rt')
        elif kind=='cells':
            self.cell(canvas,540,880,160,1,True,True,1,False)
            self.water_outflow(canvas,540,880,160,1,True)
            self.type.text(canvas,'Ice outside cells',540,620,27,ICE,anchor='mm')
            self.type.text(canvas,'Protective solutes inside',540,1110,27,AMBER,anchor='mm')
        elif kind=='glucose':
            self.type.text(canvas,'Urea',135,750,67,ICE,face='display')
            self.type.text(canvas,'builds up before freezing',135,842,29,MUTED)
            self.type.text(canvas,'Glucose',135,960,67,AMBER,face='display')
            self.type.text(canvas,'mobilised from liver stores',135,1050,29,MUTED)
            for j in range(6):
                x=805+(j%2)*90;y=790+(j//2)*100
                d.ellipse((x-15,y-15,x+15,y+15),fill=ICE if j<2 else AMBER)
        elif kind=='experiment':
            self.type.text(canvas,'REPEATED FREEZE / THAW',540,720,29,ICE,anchor='mm')
            for j in range(3):
                x=250+j*290;self.crystal(canvas,x,850,45);self.type.text(canvas,str(j+1),x,940,26,MUTED,anchor='mm')
            self.type.text(canvas,'Final freeze: −8°C',540,1070,66,PAPER,face='display',anchor='mm')
        elif kind=='recovery':
            self.type.text(canvas,'5 of 5',540,820,142,MINT,face='display',anchor='mm')
            self.type.text(canvas,'recovered',540,955,61,PAPER,face='display',anchor='mm')
            self.type.text(canvas,'Healthy through 7 weeks of follow-up',540,1060,29,MUTED,anchor='mm')
        elif kind=='scope':
            self.type.text(canvas,'Read the full paper',80,745,62,ICE,face='display')
            self.type.block(canvas,'Costanzo et al. (2015)\nPLOS ONE',82,860,36,PAPER,width=900,weight=500,max_lines=2)
            self.type.block(canvas,'Correction checked. Claims, limits and visual credits are in the research record.',82,1005,31,MUTED,width=880,weight=500,max_lines=3)
        else:raise ValueError('Unknown carousel visual kind '+kind)
        d=ImageDraw.Draw(canvas);d.line((72,1220,1008,1220),fill='#34525b',width=2)
        self.type.text(canvas,self.ep['doi'],72,1251,26,MINT,weight=600)
        if kind not in ('portrait','scope'):self.type.text(canvas,'Conceptual illustration',1008,1180,21,MUTED,weight=500,anchor='rt')
        return canvas

def render(ep,voice,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    MEDIA.mkdir(parents=True,exist_ok=True);QA.mkdir(parents=True,exist_ok=True)
    vis=Visuals(ep,out)
    for s in ep['production']['segments']:
        for c in s['captions']:
            if len(vis.type.wrap(c,59,874,'sans',650))>2:raise ValueError('Caption overflow: '+c)
        for shot in s['shots']:
            if len(vis.type.wrap(shot.get('title',''),shot.get('title_size',82),910,'display',600))>3:raise ValueError('Title overflow')
    timeline,captions,audit,duration=voice.make(ep,out)
    if not 35<=duration<=80:raise ValueError('Duration outside nature-story envelope: '+str(duration))
    if max(s['end']-s['start'] for s in timeline)>8:raise ValueError('Shot exceeds 8 seconds')
    photo_seconds=sum(s['end']-s['start'] for s in timeline if s['kind'] in ('portrait','nature','closing') or (s['kind']=='winter' and s.get('asset')))
    if photo_seconds>max(20,duration*.4):raise ValueError('Still-photo share exceeds the nature-story composition budget')
    silent=out/'picture.mp4'
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(silent)]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for i in range(math.ceil(duration*FPS)):
            t=i/FPS;shot=next((s for s in timeline if s['start']<=t<s['end']),timeline[-1])
            cap=next((c['text'] for c in captions if c['start']<=t<c['end']),'')
            proc.stdin.write(vis.frame(shot,t,cap,t/duration).tobytes())
    finally:proc.stdin.close()
    if proc.wait()!=0:raise RuntimeError('Native-HD encode failed')
    target=MEDIA/(ep['slug']+'.mp4')
    sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',silent,'-i',out/'narration.wav','-map','0:v:0','-map','1:a:0','-c:v','copy','-af','loudnorm=I=-16:TP=-2.5:LRA=7','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-shortest','-movflags','+faststart',target])
    info=json.loads(sh(['ffprobe','-v','quiet','-show_streams','-show_format','-of','json',target]).stdout)
    loud=sh(['ffmpeg','-hide_banner','-i',target,'-af','loudnorm=I=-16:TP=-2.5:LRA=7:print_format=json','-vn','-f','null','-']).stderr
    loud=json.loads(loud[loud.rfind('{'):loud.rfind('}')+1])
    if not -18<=float(loud['input_i'])<=-14 or float(loud['input_tp'])>-1:raise ValueError('Loudness/peak gate failed')
    segs,_=voice.asr.transcribe(str(target),beam_size=5,condition_on_previous_text=False)
    transcript=' '.join(s.text for s in segs);intended=' '.join(s['speech'] for s in ep['production']['segments'])
    similarity=difflib.SequenceMatcher(None,norm(intended),norm(transcript)).ratio()
    if similarity<.90:raise ValueError('Final encoded transcript mismatch')
    require_critical_terms(transcript,ep['production']['critical_terms'])
    samples=[];boundary=[]
    def sample(name,seek):
        path=QA/(ep['id'].lower()+'-'+name+'.jpg')
        sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(seek),'-i',target,'-frames:v','1','-vf','scale=540:960',path])
        return path
    for i,s in enumerate(timeline):
        path=sample(f'shot-{i+1:02}',(s['start']+s['end'])/2)
        with Image.open(path) as im:samples.append(im.resize((360,640)))
        if i:
            for side,seek in [('before',max(0,s['start']-1/FPS)),('after',s['start']+1/FPS)]:
                boundary.append('qa/'+sample(f'boundary-{i:02}-{side}',seek).name)
    grid=Image.new('RGB',(1080,640*math.ceil(len(samples)/3)),BG)
    for i,im in enumerate(samples):grid.paste(im,((i%3)*360,(i//3)*640))
    grid.save(QA/(ep['id'].lower()+'-contact.jpg'),quality=94)
    for label,seek in [('opening-0s',0),('opening-1s',1)]:boundary.append('qa/'+sample(label,seek).name)
    name=ep['id'].lower()+'-final-frame.jpg'
    sh(['ffmpeg','-hide_banner','-loglevel','error','-y','-sseof','-1','-i',target,'-vf','reverse,scale=540:960','-frames:v','1',QA/name]);boundary.append('qa/'+name)
    vis.cover().save(MEDIA/(ep['slug']+'_cover.jpg'),quality=96,subsampling=0)
    for i,s in enumerate(ep.get('slides',[])):vis.slide(s,i,len(ep['slides'])).save(MEDIA/f'{ep["slug"]}_slide_{i+1:02}.jpg',quality=96,subsampling=0)
    return {'renderer':VERSION,'declared_renderer':'nature-story-8','editorial_style':ep['production'].get('editorial_style','science-journalism'),
        'duration':float(info['format']['duration']),'native_dimensions':[W,H],'shots':timeline,'captions':captions,'segment_audio':audit,
        'final_audio_transcript':transcript,'final_script_similarity':similarity,'loudness':loud,'technical_passed':True,
        'editorial_review_required':True,'listening_review_claimed':False,'contact_sheet':f'qa/{ep["id"].lower()}-contact.jpg',
        'boundary_frame_checks':boundary,'font_receipts':vis.type.receipts,
        'asset_receipts':[{**a,'download_sha256':sha(vis.assets[a['id']])} for a in ep['production']['assets']],
        'representation':'Licensed reference photographs with editorial camera movement; original conceptual cell/process animations. No footage of experimental freezing or fabricated microscopy.',
        'reference_photo_seconds':round(photo_seconds,3),'reference_photo_share':round(photo_seconds/duration,4),
        'voice':{'model':'Kokoro v1.0','voice':'af_heart','speed':float(ep['production'].get('voice_speed',1))}}
