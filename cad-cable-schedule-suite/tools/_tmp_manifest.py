# -*- coding: utf-8 -*-
"""组装待公开仓库的文件清单（manifest.json）：仓库路径 → 源文件路径。"""
import json, pathlib
R = pathlib.Path(r'C:\Users\ASUS\Documents\DeepSeek-WorkSpace\Projects\cad-interaction-platform\cad-cable-schedule-suite')
SKILL = pathlib.Path.home() / '.dsh' / 'skills' / 'cad-cable-schedule'
OUT = pathlib.Path(r'C:\Users\ASUS\Documents\DeepSeek-WorkSpace\Projects\cad-cable-schedule')
SKIP_DIRS = {'.venv', 'dist', 'build', '__pycache__', '.pytest_cache', 'logs', 'out', '.git'}
SKIP_EXT = {'.exe', '.zip', '.pkg', '.pyz', '.pyc', '.dll', '.pyd', '.so', '.bak', '.part', '.dwg', '.cuix', '.xlsx'}
def collect(base, prefix):
    out = []
    for p in sorted(base.rglob('*')):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file() or p.suffix.lower() in SKIP_EXT:
            continue
        rel = p.relative_to(base).as_posix()
        out.append({'repo_path': f'{prefix}/{rel}', 'src': str(p)})
    return out
items = collect(R, 'cad-cable-schedule-suite') + collect(SKILL, 'skill')
manifest = {'repo': 'cad-cable-schedule', 'files': items}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'清单写出: {len(items)} 个文件')
import collections
c = collections.Counter(i['repo_path'].split('/')[0] for i in items)
for k, v in c.items():
    print(f'   {k}/  {v} 个')
tot = sum(pathlib.Path(i['src']).stat().st_size for i in items)
print(f'合计 {tot/1024:.0f} KB')