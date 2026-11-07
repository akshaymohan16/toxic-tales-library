#!/usr/bin/env python3
"""Sources, neural films, and publication candidates tied to exact reviewed bytes."""
import hashlib, html, json, os, re
from datetime import datetime, timezone
from pathlib import Path
from production import ROOT, MEDIA, QA, CACHE, VERSION, Voice, render, sha, norm
REPO='akshaymohan16/toxic-tales-library';SITE=ROOT/'site'
def read(p,default=None):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
def write(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
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
    for p in ep['posts']:
        assert p['format'] in ['REEL','CAROUSEL'] and datetime.fromisoformat(p['publication_date']).tzinfo
        assert ep['doi'] in p['caption'] and len(p['caption'])<=2200
    if any(p['format']=='CAROUSEL' for p in ep['posts']):assert 5<=len(ep['slides'])<=8

def release_ok(a,m):
    return bool(a and a.get('decision')=='release' and a.get('fingerprint')==m['fingerprint'] and a.get('files')==m['files'] and a.get('evidence_sha256')==m['evidence_sha256'] and all(a.get(k) for k in ['reviewed_contact_sheet','scientific_review','visual_review','audio_review']))

def main():
    assert os.environ.get('GITHUB_REPOSITORY',REPO)==REPO,'Repository boundary'
    for d in [MEDIA,QA,CACHE]:d.mkdir(parents=True,exist_ok=True)
    config=read(ROOT/'automation/config.json',{});approvals=read(ROOT/'quality/releases.json',{});cache=read(CACHE/'index.json',{})
    ledger=read(ROOT/'automation/published.json',{'posts':[]})
    receipts={p['post_id']:p for p in ledger.get('posts',[])}
    papers=[];candidates=[];queue=[];voice=None;ids=set()
    for path in sorted((ROOT/'episodes').glob('*.json')):
        ep=read(path)
        if not ep.get('production'):continue
        validate(ep);evidence_path=ROOT/ep['evidence_file']
        fp=hashlib.sha256(path.read_bytes()+evidence_path.read_bytes()+(ROOT/'scripts/production.py').read_bytes()+(ROOT/'requirements.txt').read_bytes()).hexdigest()
        stem=ep['slug']+'-'+fp[:12]
        qa_path=QA/(ep['id'].lower()+'.json');m=read(qa_path,{})
        valid=cache.get(ep['id'])==fp and m.get('fingerprint')==fp and m.get('files') and all((SITE/p).exists() and sha(SITE/p)==h for p,h in m['files'].items())
        if not valid:
            if voice is None:voice=Voice()
            out=CACHE/ep['id'];out.mkdir(parents=True,exist_ok=True)
            m=render(ep,voice,out)
            files=[]
            originals=[MEDIA/(ep['slug']+'.mp4'),MEDIA/(ep['slug']+'_cover.jpg')]+[MEDIA/f'{ep["slug"]}_slide_{i+1:02}.jpg' for i in range(len(ep.get('slides',[])))]
            for original in originals:
                target=original.with_name(original.name.replace(ep['slug'],stem,1));original.replace(target);files.append(target)
            m.update(fingerprint=fp,evidence_sha256=sha(evidence_path),files={p.relative_to(SITE).as_posix():sha(p) for p in files})
            write(qa_path,m);cache[ep['id']]=fp;write(CACHE/'index.json',cache)
        media={'reel':f'media/{stem}.mp4','cover':f'media/{stem}_cover.jpg','slides':[f'media/{stem}_slide_{i+1:02}.jpg' for i in range(len(ep.get('slides',[])))]}
        entry={k:ep.get(k) for k in ('id','slug','title','hook','doi','paper_title','citation','summary','evidence_note','source_url','tags')}
        entry.update(media=media,evidence=ep['evidence'],credits=ep['production']['assets'],qa=f'qa/{ep["id"].lower()}.json',evidence_record=f'sources/{ep["id"].lower()}.html')
        entry['publications']=[{'post_id':p['post_id'],'format':p.get('format'),'status':p.get('status'),'public_url':p.get('public_url'),'date':p.get('publication_date')} for p in receipts.values() if p.get('episode_id')==ep['id']]
        papers.append(entry)
        rows=''.join('<li>'+html.escape(c['claim'])+' <em>('+html.escape(c['location'])+')</em></li>' for c in ep['evidence']['claims'])
        credits=''.join('<li>'+html.escape(a['creator'])+' — <a href="'+html.escape(a['source_page'],quote=True)+'">Source</a> · <a href="'+html.escape(a['license_url'],quote=True)+'">'+html.escape(a['license'])+'</a>. '+html.escape(a['changes'])+'</li>' for a in ep['production']['assets'])
        page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+html.escape(ep['title'])+'</title><style>body{max-width:800px;margin:40px auto;padding:20px;font:18px/1.6 system-ui;background:#071c24;color:#fffdf2}a{color:#cefa4c}li{margin-bottom:16px}pre{white-space:pre-wrap;font:14px/1.6 system-ui}</style><a href="../">Toxic Tales research archive</a><h1>'+html.escape(ep['title'])+'</h1><p>'+html.escape(ep['citation'])+' · <a href="'+ep['source_url']+'">'+ep['doi']+'</a></p><h2>Claims and source locations</h2><ul>'+rows+'</ul><h2>Limits</h2><p>'+html.escape(ep['evidence_note'])+'</p><h2>Media credits</h2><p>Reference imagery and explanatory animation; not footage or raw data from this experiment. Narration is synthetic.</p><ul>'+credits+'</ul><h2>Verification record</h2><pre>'+html.escape(evidence_path.read_text(encoding='utf-8'))+'</pre>'
        target=SITE/entry['evidence_record'];target.parent.mkdir(exist_ok=True);target.write_text(page,encoding='utf-8')
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

