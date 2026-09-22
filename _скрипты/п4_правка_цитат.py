# -*- coding: utf-8 -*-
"""In-place quote repair for P4/P5 after O4 reject."""
import json, os, re, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROMPT = os.path.join(ROOT, "_промты", "П4_правка_цитат.md")
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

def _set(obj, path, value):
    cur = obj
    parts = []
    tail = path
    while tail:
        if tail[0] == '[':
            i = tail.index(']')
            parts.append(int(tail[1:i]))
            tail = tail[i + 1:]
            if tail.startswith('.'):
                tail = tail[1:]
        else:
            br, dot = tail.find('['), tail.find('.')
            if br != -1 and (dot == -1 or br < dot):
                key, tail = tail[:br], tail[br:]
            elif dot != -1:
                key, tail = tail.split('.', 1)
            else:
                key, tail = tail, ''
            parts.append(key)
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value

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
    o4 = _mod('o4', 'o4_скоринг.py')
    b4 = _mod('b4', 'b4_проверка_выжимок.py')
    map_p = os.path.join(folder, '04_карта.json')
    plots_p = os.path.join(folder, '10_сюжеты_сведены.json')
    p4_p = os.path.join(folder, '11_проверка.json')
    p5_p = os.path.join(folder, '12_скоринг.json')
    if not all(os.path.isfile(p) for p in (map_p, plots_p, p4_p)):
        print('p4 quote repair: missing inputs')
        return 1
    card = json.load(open(map_p, encoding='utf-8'))
    plots = json.load(open(plots_p, encoding='utf-8'))
    p4 = json.load(open(p4_p, encoding='utf-8'))
    p5 = json.load(open(p5_p, encoding='utf-8')) if os.path.isfile(p5_p) else {'темы': []}
    files = {'11_проверка.json': p4, '12_скоринг.json': p5}
    check = getattr(o4, 'проверить_цитаты')
    norm = getattr(b4, 'норм')
    src = {'карта': card, 'сюжеты': plots}
    bad = check(src, files)
    if not bad:
        print('p4 quote repair: no foreign quotes')
        return 1
    pool = list(dict.fromkeys(_strings(src)))
    left = []
    joined = '\n'.join(norm(s) for s in pool)
    for name, path, q in bad:
        repl = pick(q, pool, norm)
        if repl is None or norm(repl) not in joined:
            left.append((name, path, q))
            continue
        _set(files[name], path, repl)
        print(f'  · {name} {path}: input string')
    if left:
        model = _mod('модель', 'модель.py')
        on = getattr(model, 'включен')
        ask = getattr(model, 'спросить')
        if not on() or not os.path.isfile(PROMPT):
            print('p4 quote repair: API needed for', len(left), 'quotes')
            return 1
        prompt = open(PROMPT, encoding='utf-8').read().strip()
        pool_q = [s for s in pool if len(s) >= 40][:80]
        usage = {'prompt_tokens': 0, 'completion_tokens': 0}
        print(f'    API P4 quote repair: quotes={len(left)}')
        user = '\n'.join([
            '## input strings', '```json',
            json.dumps(pool_q, ensure_ascii=False, indent=2),
            '```', '', '## O4 reject', '```json',
            json.dumps([{'файл': n, 'путь': p, 'цитата': q} for n, p, q in left], ensure_ascii=False, indent=2),
            '```', '',
            'Return JSON {"замены": [{"файл", "путь", "цитата"}, ...]}.',
        ])
        obj, u = ask([{'role': 'system', 'content': prompt}, {'role': 'user', 'content': user}], effort='medium')
        usage['prompt_tokens'] += int((u or {}).get('prompt_tokens') or 0)
        usage['completion_tokens'] += int((u or {}).get('completion_tokens') or 0)
        for z in (obj or {}).get('замены') or []:
            name, path, q = z.get('файл'), z.get('путь'), z.get('цитата')
            if name not in files or not path or not q:
                continue
            if norm(q) not in joined:
                print(f'  · {name} {path}: model quote not in input')
                continue
            _set(files[name], path, q)
        print(f'p4 quote repair: API in {usage["prompt_tokens"]}, out {usage["completion_tokens"]}')
    json.dump(p4, open(p4_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(p4_p, 'a', encoding='utf-8').write('\n')
    if os.path.isfile(p5_p):
        json.dump(p5, open(p5_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        open(p5_p, 'a', encoding='utf-8').write('\n')
    still = check(src, files)
    if still:
        print(f'p4 quote repair: still foreign {len(still)}')
        return 1
    print('p4 quote repair: quotes from map/plots')
    return 0

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('python3 script folder')
    raise SystemExit(main(sys.argv[1]))

