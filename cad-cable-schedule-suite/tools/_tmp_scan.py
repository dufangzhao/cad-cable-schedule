# -*- coding: utf-8 -*-
import pathlib, re
R = pathlib.Path(r'C:\Users\ASUS\Documents\DeepSeek-WorkSpace\Projects\cad-interaction-platform\cad-cable-schedule-suite')
SKILL = pathlib.Path.home() / '.dsh' / 'skills' / 'cad-cable-schedule'
SKIP_DIRS = {'.venv', 'dist', 'build', '__pycache__', '.pytest_cache', 'logs', 'out', '.git'}
SKIP_EXT = {'.exe', '.zip', '.pkg', '.pyz', '.pyc', '.dll', '.pyd', '.so', '.bak', '.part', '.dwg'}
PATTERNS = {
    '真实客户/项目名': r'哈密|培训学习',
    '本机绝对路径': r'C:\\\\Users\\\\ASUS',
    '内网平台': r'127\.0\.0\.1/api|kpt_|知识库平台|ApplicationPlugins\\\\Cable',
    'AutoCAD 产品码': r'ACAD-\d{4}',
    '令牌/密码字样': r'(?i)(token|password|secret|api[_-]?key)\s*[=:]\s*[^\s]{8,}',
    '邮箱': r'[\w.]+@[\w.]+\.\w+',
}
def collect(base):
    out = []
    for p in base.rglob('*'):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() not in SKIP_EXT:
            out.append(p)
    return out
files = collect(R) + collect(SKILL)
for label, pat in PATTERNS.items():
    rx = re.compile(pat)
    hits = []
    for p in files:
        try:
            text = p.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append((p.name, i, line.strip()[:78]))
    print(f'### {label}: {len(hits)} 处')
    for n, i, t in hits[:6]:
        print(f'    {n}:{i}  {t}')