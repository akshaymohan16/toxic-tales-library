"""ASCII-safe transport for UTF-8 source files through Windows tool output."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
entries=[]
for p in root.rglob('*'):
    if p.is_file() and p.suffix in ('.py','.json','.md','.yml','.txt','.html') and '__pycache__' not in p.parts:
        entries.append({'path':p.relative_to(root).as_posix(),'mode':'100644','type':'blob','content':p.read_text(encoding='utf-8')})
print(json.dumps(entries,ensure_ascii=True))
