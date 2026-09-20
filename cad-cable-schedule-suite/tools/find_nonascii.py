# -*- coding: utf-8 -*-
import sys
from pathlib import Path
p = Path(sys.argv[1])
for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
    hits = [(c, hex(ord(c))) for c in line if ord(c) > 127]
    if hits:
        print(f"{i}: {hits}  ->  {line.strip()[:90]}")
