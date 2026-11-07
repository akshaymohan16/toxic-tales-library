#!/usr/bin/env python3
"""Sources, neural films, and publication candidates tied to exact reviewed bytes."""
import hashlib, html, json, os, re
from datetime import datetime, timezone
from pathlib import Path
import production as story_renderer
import production_v4 as legacy_renderer
import production_pilot as pilot_renderer
from editorial_gate import STANDARD, validate_pre_render, final_editorial_ok
from production import ROOT, MEDIA, QA, CACHE, VERSION, sha, norm
REPO='akshaymohan16/toxic-tales-library';SITE=ROOT/'site'
def read(p,default=None):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
def write(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')

def page_shell(title,body,script=''):
    style='''
    :root{color-scheme:dark;--bg:#080b0a;--panel:#111916;--line:#2d4036;--lime:#c8ff36;--text:#f6f8f1;--muted:#a9bdb2}*{box-sizing:border-box}
    body{margin:0;background:radial-gradient(ellipse at 90% 0,#183025 0,transparent 48%),var(--bg);color:var(--text);font:17px/1.65 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:30px 24px 65px}nav{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:22px}.brand{color:var(--lime);font-size:19px;font-weight:900;letter-spacing:.15em}a{color:var(--lime);text-underline-offset:4px}h1{font-size:clamp(36px,6vw,64px);line-height:1.08;letter-spacing:-.04em;margin:14px 0 20px}h2{font-size:25px;line-height:1.2;margin:0 0 15px}h3{font-size:17px;color:var(--lime);margin:0 0 8px}p{margin:10px 0}.muted{color:var(--muted)}.eyebrow{font-size:12px;font-weight:800;color:var(--lime);letter-spacing:.15em;text-transform:uppercase}.hero{padding:38px 0 28px;max-width:900px}.lede{font-size:21px;color:var(--muted)}.badge{display:inline-block;border:1px solid #62793b;background:#1c2812;padding:6px 11px;border-radius:5px;color:var(--lime);font-size:12px;font-weight:800;letter-spacing:.08em}.actions{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0}.button{display:inline-block;padding:11px 16px;background:var(--lime);color:#080b0a;border:1px solid var(--lime);border-radius:6px;text-decoration:none;font:700 14px/1.4 system-ui;cursor:pointer}.button.secondary{background:transparent;color:var(--text);border-color:#5c7565}.panel{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:25px;margin:0 0 22px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.overview{margin-bottom:26px}.overview .panel{margin:0}.overview .wide{grid-column:1/-1}.pilot-grid{display:grid;grid-template-columns:minmax(260px,360px) minmax(0,1fr);gap:34px;align-items:start}.film{position:sticky;top:24px}.film video{display:block;width:100%;aspect-ratio:9/16;background:#000;border:1px solid var(--line);border-radius:12px}.film p{font-size:13px}.caption{width:100%;min-height:470px;resize:vertical;background:#080d0a;color:var(--text);padding:17px;border:1px solid #45614f;border-radius:6px;font:14px/1.65 system-ui}.cover{display:flex;gap:20px;align-items:flex-start}.cover img{width:132px;aspect-ratio:9/16;object-fit:cover;border-radius:6px}.cover p{font-size:14px}ul{padding-left:23px}li{margin-bottom:14px}.source-location{display:block;color:var(--muted);font-size:14px;margin-top:5px}.citation{font-size:15px;color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.65 system-ui;color:var(--muted)}details summary{cursor:pointer;color:var(--lime);font-weight:700}footer{border-top:1px solid var(--line);padding-top:22px;margin-top:36px;color:var(--muted);font-size:13px}a:focus-visible,button:focus-visible,textarea:focus-visible,summary:focus-visible{outline:3px solid var(--lime);outline-offset:4px}@media(max-width:720px){main{padding:22px 17px 45px}.pilot-grid,.grid{grid-template-columns:1fr}.film{position:static;max-width:360px;margin:auto;width:100%}.overview .wide{grid-column:auto}.panel{padding:20px}.hero{padding-top:28px}.caption{min-height:430px}.cover img{width:110px}}
    '''
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#080b0a"><title>'+html.escape(title)+' | Toxic Tales</title><style>'+style+'</style></head><body><main>'+body+'</main>'+script+'</body></html>'

def research_page(ep,entry,evidence_text):
    esc=html.escape;story=ep.get('editorial_story',{})
    question=story.get('question') or ep.get('hook') or ep['title']
    importance=story.get('why_it_matters') or 'This entry explains the original finding, its ecological meaning and the limits of the evidence.'
    rows=''.join('<li>'+esc(c['claim'])+'<span class="source-location">'+esc(c['location'])+'</span></li>' for c in ep['evidence']['claims'])
    limits=''.join('<li>'+esc(x)+'</li>' for x in ep['evidence']['limitations'])
    credits=''.join('<li>'+esc(a['creator'])+' &mdash; <a href="'+esc(a['source_page'],quote=True)+'">Original media</a> &middot; <a href="'+esc(a['license_url'],quote=True)+'">'+esc(a['license'])+'</a><span class="source-location">'+esc(a['changes'])+'</span></li>' for a in ep['production']['assets'])
    contexts=''.join('<li><a href="'+esc(c['url'],quote=True)+'">'+esc(c['citation'])+'</a><span class="source-location">'+esc(c.get('scope',''))+'</span></li>' for c in story.get('context_sources',[]))
    body='<nav><span class="brand">TOXIC TALES</span><a href="../">Research archive</a></nav><header class="hero"><div class="eyebrow">Research behind the Reel &middot; '+esc(ep['id'])+'</div><h1>'+esc(ep['title'])+'</h1><p class="lede">'+esc(question)+'</p><p class="citation">'+esc(ep['paper_title'])+'<br>'+esc(ep['citation'])+'</p><div class="actions"><a class="button" href="'+esc(ep['evidence']['full_text_url'],quote=True)+'">Read the full paper</a><a class="button secondary" href="'+esc(ep['source_url'],quote=True)+'">DOI: '+esc(ep['doi'])+'</a></div></header>'
    body+='<div class="grid overview"><section class="panel"><h3>Why it matters</h3><p>'+esc(importance)+'</p></section><section class="panel"><h3>What the study found</h3><p>'+esc(ep['summary'])+'</p></section><section class="panel wide"><h3>What this does not establish</h3><p>'+esc(ep['evidence_note'])+'</p><ul>'+limits+'</ul></section></div>'
    body+='<section class="panel"><h2>Claims you can trace</h2><p class="muted">Each factual claim is tied to its location in the original research. Background evidence is listed separately.</p><ul>'+rows+'</ul></section>'
    citation_links=[]
    for ext in ['bib','ris']:
        source=ROOT/'citations'/(ep['id'].lower()+'.'+ext)
        if source.exists():
            target=SITE/'citations'/source.name;target.parent.mkdir(exist_ok=True)
            target.write_bytes(source.read_bytes())
            citation_links.append('<a class="button secondary" href="../citations/'+source.name+'" download>'+('BibTeX' if ext=='bib' else 'RIS')+'</a>')
    if citation_links:body+='<section class="panel"><h2>Save the reference</h2><div class="actions">'+''.join(citation_links)+'</div></section>'
    if contexts:body+='<section class="panel"><h2>Research that supplies the context</h2><ul>'+contexts+'</ul></section>'
    body+='<section class="panel"><h2>Visual sources and credits</h2><p class="muted">Reference imagery and explanatory animation are not footage or raw data from this experiment. Narration is synthetic.</p><ul>'+credits+'</ul></section><section class="panel"><details><summary>Complete verification record</summary><pre>'+esc(evidence_text)+'</pre></details></section><footer><p>Verified '+esc(ep['evidence']['checked_at'])+'. Paper links lead to the authors\' or publisher\'s source; this archive does not redistribute publisher PDFs.</p><a href="../">Return to Research Behind Toxic Tales</a></footer>'
    return page_shell(ep['title']+' — Research',body)

def pilot_page(ep,entry,manifest,config,receipts):
    esc=html.escape;post=next(p for p in ep['posts'] if p['format']=='REEL');receipt=receipts.get(post['id'],{})
    published=receipt.get('status')=='published' and receipt.get('public_url')
    held=config.get('publishing_paused',True) or not ep.get('publication_enabled')
    state='PUBLISHED' if published else ('UNPUBLISHED / AWAITING OWNER APPROVAL' if held else 'PREPARED REEL / NOT YET PUBLISHED')
    status_text='This is the finished post package. Publication is on hold until you approve the pilot.' if held and not published else ('The Reel is published on Instagram.' if published else 'This preview is not evidence of publication. The public Instagram link appears here only after confirmed publication.')
    links='<a class="button" href="'+esc(entry['evidence_record'],quote=True)+'">Research behind this Reel</a><a class="button secondary" href="'+esc(ep['evidence']['full_text_url'],quote=True)+'">Read the full paper</a>'
    if published:links+='<a class="button secondary" href="'+esc(receipt['public_url'],quote=True)+'">View on Instagram</a>'
    body='<nav><span class="brand">TOXIC TALES</span><a href="./">Research archive</a></nav><header class="hero"><span class="badge">'+state+'</span><h1>'+esc(ep['title'])+'</h1><p class="lede">'+esc(ep['hook'])+'</p><p class="muted">'+status_text+'</p></header><div class="pilot-grid"><section class="film" aria-label="Reel preview"><video controls playsinline preload="metadata" poster="'+esc(entry['media']['cover'],quote=True)+'"><source src="'+esc(entry['media']['reel'],quote=True)+'" type="video/mp4">Your browser does not support embedded video.</video><p class="muted">@toxic_tales_eco &middot; Vertical Reel &middot; Synthetic narration</p><a href="'+esc(entry['media']['reel'],quote=True)+'">Open the video file</a></section><div><section class="panel"><div class="eyebrow">The complete post</div><h2>Caption</h2><p class="muted">This is the exact text prepared for Instagram.</p><textarea class="caption" id="caption" readonly aria-label="Complete Instagram caption">'+esc(post['caption'])+'</textarea><div class="actions"><button class="button" id="copy-caption" type="button">Copy caption</button><span class="muted" id="copy-status" role="status" aria-live="polite"></span></div></section><section class="panel cover"><a href="'+esc(entry['media']['cover'],quote=True)+'"><img src="'+esc(entry['media']['cover'],quote=True)+'" alt="Reel cover: '+esc(ep['production'].get('cover_title',ep['title']),quote=True)+'"></a><div><h2>Cover</h2><p>The cover is supplied with the video and caption.</p><a href="'+esc(entry['media']['cover'],quote=True)+'">Open full-size cover</a></div></section><section class="panel"><h2>The paper behind it</h2><p>'+esc(ep['paper_title'])+'</p><p class="citation">'+esc(ep['citation'])+'<br><a href="'+esc(ep['source_url'],quote=True)+'">'+esc(ep['doi'])+'</a></p><p class="muted">The archive includes the study design, claim-by-claim checks, limitations, supporting papers and visual credits.</p><div class="actions">'+links+'</div></section></div></div><footer><p>Previewing or copying this post does not publish it. The original paper remains linked from the permanent research record.</p></footer>'
    script='''<script>document.getElementById('copy-caption').addEventListener('click',async()=>{const field=document.getElementById('caption'),status=document.getElementById('copy-status');try{await navigator.clipboard.writeText(field.value);status.textContent='Caption copied.';}catch(error){field.focus();field.select();status.textContent='Caption selected. Use your device copy command.';}});</script>'''
    return page_shell('Pilot preview — '+ep['title'],body,script)
def validate(ep):
    assert re.fullmatch(r'[a-z0-9-]+',ep['slug'])
    assert re.fullmatch(r'10\.\d{4,9}/\S+',ep['doi'])
    evidence=ep['evidence'];plan=ep['production']
    for f in ['full_text_url','checked_at','design','claims','limitations','correction_check']:assert evidence.get(f),f'Missing {f}'
    assert (ROOT/ep['evidence_file']).is_file(),'Missing claim record'
    assert len(evidence['claims'])>=3 and all(c.get('claim') and c.get('location') for c in evidence['claims'])
    assert 7<=len(plan['segments'])<=12
    for s in plan['segments']:
        assert norm(' '.join(s['captions']))==norm(s['speech']),'Caption/script mismatch'
        assert all(len(c)<=83 for c in s['captions'])
        assert s['shots'] and s['shots'][0].get('start',0)==0 and s['shots'][-1].get('end',1)==1
        for a,b in zip(s['shots'],s['shots'][1:]):assert a.get('end',1)==b.get('start',0),'Shot gap'
    assert len({s['kind'] for x in plan['segments'] for s in x['shots']})>=5
    assert plan['assets'] and all(a.get('creator') and a.get('license_url') and a.get('source_page') and a.get('changes') for a in plan['assets'])
    if plan.get('editorial_style')=='science-journalism':
        story=ep.get('editorial_story',{})
        for key in ['question','why_it_matters','narrative_arc','closing_payoff']:
            assert story.get(key),'Missing journalism reporting element: '+key
        if plan.get('editorial_standard') != STANDARD:
            assert len(story.get('context_sources',[]))>=2,'Context needs separately verified published sources'
        else:
            assert isinstance(story.get('context_sources'),list),'Context source list is required, and may be empty when all claims come from the focal paper'
    for p in ep['posts']:
        assert p['format'] in ['REEL','CAROUSEL'] and datetime.fromisoformat(p['publication_date']).tzinfo
        assert ep['doi'] in p['caption'] and len(p['caption'])<=2200
    if any(p['format']=='CAROUSEL' for p in ep['posts']):assert 5<=len(ep['slides'])<=8

def release_ok(a,m):
    if not final_editorial_ok(a,m):return False
    if m.get('editorial_style')=='science-journalism' and not (a and a.get('narrative_review')):return False
    return bool(a and a.get('decision')=='release' and a.get('fingerprint')==m['fingerprint'] and a.get('files')==m['files'] and a.get('evidence_sha256')==m['evidence_sha256'] and all(a.get(k) for k in ['reviewed_contact_sheet','scientific_review','visual_review','audio_review']))

def main():
    assert os.environ.get('GITHUB_REPOSITORY',REPO)==REPO,'Repository boundary'
    for d in [MEDIA,QA,CACHE]:d.mkdir(parents=True,exist_ok=True)
    config=read(ROOT/'automation/config.json',{});approvals=read(ROOT/'quality/releases.json',{});cache=read(CACHE/'index.json',{})
    ledger=read(ROOT/'automation/published.json',{'posts':[]})
    receipts={p['post_id']:p for p in ledger.get('posts',[])}
    papers=[];candidates=[];queue=[];voices={};ids=set()
    for path in sorted((ROOT/'episodes').glob('*.json')):
        ep=read(path)
        if not ep.get('production'):continue
        validate(ep);evidence_path=ROOT/ep['evidence_file']
        editorial_source=validate_pre_render(ep,evidence_path.read_text(encoding='utf-8'))
        renderer=pilot_renderer if ep['production'].get('renderer')=='ecology-story-7' else (story_renderer if ep['production'].get('editorial_style')=='science-journalism' else legacy_renderer)
        fingerprint_bytes=path.read_bytes()+evidence_path.read_bytes()+Path(renderer.__file__).read_bytes()+(ROOT/'requirements.txt').read_bytes()
        if editorial_source:
            for dependency in ['scripts/production.py','scripts/editorial_gate.py','quality/SCIENCE_JOURNALISM.md','quality/VISUAL_STANDARD.md','quality/PRODUCTION_STANDARD.md']:
                fingerprint_bytes+=(ROOT/dependency).read_bytes()
        fp=hashlib.sha256(fingerprint_bytes).hexdigest()
        stem=ep['slug']+'-'+fp[:12]
        qa_path=QA/(ep['id'].lower()+'.json');m=read(qa_path,{})
        valid=cache.get(ep['id'])==fp and m.get('fingerprint')==fp and m.get('files') and all((SITE/p).exists() and sha(SITE/p)==h for p,h in m['files'].items())
        if not valid:
            if renderer.VERSION not in voices:voices[renderer.VERSION]=renderer.Voice()
            out=CACHE/ep['id'];out.mkdir(parents=True,exist_ok=True)
            m=renderer.render(ep,voices[renderer.VERSION],out)
            files=[]
            originals=[MEDIA/(ep['slug']+'.mp4'),MEDIA/(ep['slug']+'_cover.jpg')]+[MEDIA/f'{ep["slug"]}_slide_{i+1:02}.jpg' for i in range(len(ep.get('slides',[])))]
            for original in originals:
                target=original.with_name(original.name.replace(ep['slug'],stem,1));original.replace(target);files.append(target)
            m.update(fingerprint=fp,evidence_sha256=sha(evidence_path),files={p.relative_to(SITE).as_posix():sha(p) for p in files})
            if editorial_source:
                m.update(editorial_standard=STANDARD,editorial_source_sha256=editorial_source,pre_render_reviewer=ep['editorial_review']['reviewer'],script_author=ep.get('script_author',ep['production'].get('script_author','Toxic Tales production editor')))
            write(qa_path,m);cache[ep['id']]=fp;write(CACHE/'index.json',cache)
        media={'reel':f'media/{stem}.mp4','cover':f'media/{stem}_cover.jpg','slides':[f'media/{stem}_slide_{i+1:02}.jpg' for i in range(len(ep.get('slides',[])))]}
        entry={k:ep.get(k) for k in ('id','slug','title','hook','doi','paper_title','citation','summary','evidence_note','source_url','tags')}
        entry.update(media=media,evidence=ep['evidence'],credits=ep['production']['assets'],qa=f'qa/{ep["id"].lower()}.json',evidence_record=f'sources/{ep["id"].lower()}.html')
        entry['publications']=[{'post_id':p['post_id'],'format':p.get('format'),'status':p.get('status'),'public_url':p.get('public_url'),'date':p.get('publication_date')} for p in receipts.values() if p.get('episode_id')==ep['id']]
        if ep['id']==config.get('active_pilot_id','TT-003'):
            entry['preview_url']='pilot.html'
            entry['pilot_unpublished']=not any(p.get('status')=='published' and p.get('public_url') for p in entry['publications'] if p.get('format')=='REEL')
        papers.append(entry)
        page=research_page(ep,entry,evidence_path.read_text(encoding='utf-8'))
        target=SITE/entry['evidence_record'];target.parent.mkdir(exist_ok=True);target.write_text(page,encoding='utf-8')
        if ep['id']==config.get('active_pilot_id','TT-003'):
            (SITE/'pilot.html').write_text(pilot_page(ep,entry,m,config,receipts),encoding='utf-8')
        approved=release_ok(approvals.get(ep['id']),m)
        for p in ep['posts']:
            assert p['id'] not in ids,'Duplicate post ID';ids.add(p['id'])
            item={**p,'episode_id':ep['id'],'doi':ep['doi'],'source_slug':ep['slug'],'cover':media['cover'],'media':[media['reel']] if p['format']=='REEL' else media['slides'],'fingerprint':fp,'media_sha256':m['files'],'qa':entry['qa'],'scientifically_reviewed':True,'is_ai_generated':True,'quality_released':approved}
            candidates.append(item)
            if approved and not config.get('publishing_paused',True) and ep.get('publication_enabled') and p.get('status')!='published' and receipts.get(p['id'],{}).get('status') not in ('published','scheduled'):queue.append(item)
    assert sum(p.stat().st_size for p in SITE.rglob('*') if p.is_file())<900_000_000
    for name,obj in [('papers.json',papers),('candidates.json',candidates),('publish-queue.json',queue)]:write(SITE/name,obj)
    write(SITE/'health.json',{'repository':REPO,'commit':os.environ.get('GITHUB_SHA','local'),'built_at':datetime.now(timezone.utc).isoformat(),'renderer':VERSION,'episodes':len(papers),'queue_count':len(queue),'publishing_paused':config.get('publishing_paused',True),'note':'Deployment is not publication. Publisher must reconcile receipts.'})
    (SITE/'.nojekyll').touch()
    print(f'Rendered {len(papers)} stories; {len(queue)} released candidates.')
if __name__=='__main__':main()

