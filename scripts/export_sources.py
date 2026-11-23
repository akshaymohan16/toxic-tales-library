"""ASCII-safe transport for UTF-8 source files through Windows tool output."""
import json, sys, hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
entries=[]
for p in root.rglob('*'):
    if p.is_file() and p.suffix in ('.py','.json','.md','.yml','.txt','.html','.bib','.ris') and '__pycache__' not in p.parts:
        entries.append({'path':p.relative_to(root).as_posix(),'mode':'100644','type':'blob','content':p.read_text(encoding='utf-8')})
if '--index' in sys.argv:
    print(json.dumps([{'path':e['path'],'sha':hashlib.sha1(b'blob '+str(len(e['content'].encode())).encode()+b'\x00'+e['content'].encode()).hexdigest()} for e in entries]))
else:
    if len(sys.argv)>1:entries=[e for e in entries if e['path'] in sys.argv[1:]]
    print(json.dumps(entries,ensure_ascii=True))
