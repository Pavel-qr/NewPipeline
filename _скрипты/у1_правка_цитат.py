# -*- coding: utf-8 -*-
"""In-place U1 quote repair after о_уровень reject."""
import json, os, re, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ELLIPSIS = re.compile(r'\[\s*(?:\u2026|\.\.\.)\s*\]')

def _mod(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def _strings(obj):
    if isinstance(obj, str):
        if obj.strip():
            yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)

def pick(quote, pool, norm):
    q = (quote or '').strip()
    if not q:
        return None
    n = norm(q)
    exact = [s for s in pool if norm(s) == n]
    if exact:
        return exact[0]
    bits = [k.strip() for k in ELLIPSIS.split(q) if k.strip()]
    anchor = norm(bits[0])[:48] if bits else n[:48]
    if not anchor:
        return None
    cands = [s for s in pool if anchor in norm(s)]
    if not cands:
        return None
    return max(cands, key=len)

def main(folder):
    b4 = _mod('b4', 'b4_проверка_выжимок.py')
    agg_p = os.path.join(folder, '04_агрегат.json')
    u1_p = os.path.join(folder, '00_уровень.jsonl')
    if not all(os.path.isfile(p) for p in (agg_p, u1_p)):
        print('u1 quote repair: missing inputs')
        return 1
    agg = json.load(open(agg_p, encoding='utf-8'))
    rows = [json.loads(l) for l in open(u1_p, encoding='utf-8') if l.strip()]
    pool = list(dict.fromkeys(_strings(agg)))
    norm = getattr(b4, 'норм')
    joined = '\n'.join(norm(s) for s in pool)
    n = 0
    for row in rows:
        for u in row.get('уровни') or []:
            if not u.get('закрыт'):
                continue
            q = u.get('цитата')
            if not q or norm(q) in joined:
                continue
            repl = pick(q, pool, norm)
            if repl is None or norm(repl) not in joined:
                print(f'  · {row.get("тема")} L{u.get("уровень")}: no input string')
                return 1
            u['цитата'] = repl
            n += 1
            print(f'  · {row.get("тема")} L{u.get("уровень")}: input string')
    with open(u1_p, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'u1 quote repair: fixed {n}')
    return 0 if n else 1

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('python3 script folder')
    raise SystemExit(main(sys.argv[1]))

