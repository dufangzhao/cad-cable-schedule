# -*- coding: utf-8 -*-
import pathlib, collections
R = pathlib.Path(r'C:\Users\ASUS\Documents\DeepSeek-WorkSpace\Projects\cad-interaction-platform\cad-cable-schedule-suite')
SKILL = pathlib.Path.home() / '.dsh' / 'skills' / 'cad-cable-schedule'
SKIP_DIRS = {'.venv', 'dist', 'build', '__pycache__', '.pytest_cache', 'logs', 'out', '.git', 'node_modules'}
SKIP_EXT = {'.exe', '.zip', '.pkg', '.pyz', '.pyc', '.dll', '.pyd', '.so', '.bak'}
def collect(base):
    out = []
    for p in base.rglob('*'):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() not in SKIP_EXT:
            out.append(p)
    return out
files = collect(R)
skill = collect(SKILL)
total = sum(p.stat().st_size for p in files) + sum(p.stat().st_size for p in skill)
print(f'插件/工程源码: {len(files)} 个文件')
print(f'skill 侧:      {len(skill)} 个文件')
print(f'合计:          {len(files)+len(skill)} 个文件, {total/1024/1024:.2f} MB')
print()
c = collections.Counter(p.suffix.lower() or '(无扩展名)' for p in files + skill)
print('扩展名分布:', ', '.join(f'{k}×{v}' for k, v in c.most_common(10)))
print()
print('=== 文档类文件（需人工确认无内部信息）===')
for p in sorted(files + skill):
    if p.suffix.lower() in ('.md', '.txt'):
        print('  ', str(p.relative_to(R if p in files else SKILL)), p.stat().st_size)
print()
print('=== 最大的 5 个文本文件 ===')
for p in sorted(files + skill, key=lambda x: -x.stat().st_size)[:5]:
    print(f'   {p.stat().st_size/1024:8.1f} KB  {p.name}')