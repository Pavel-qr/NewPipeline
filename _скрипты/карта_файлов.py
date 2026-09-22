# -*- coding: utf-8 -*-
"""
Карта файловых зависимостей пайплайна.
Вход:  папка `_скрипты` (по умолчанию — та, где лежит этот файл)
Выход: в stdout — кто какой файл читает и пишет, плюс подозрительные места

  python3 _скрипты/карта_файлов.py

Зачем. Вопрос «откуда берётся этот файл и кто его читает» нельзя решать по памяти:
пересказ устройства — ровно то место, где заводятся уверенные неточности. Здесь
ответ извлекается из кода: разбирается AST каждого скрипта, ищутся вызовы open(),
имя достаётся из строкового литерала — прямо в вызове, через переменную или через
os.path.join. Модельные шаги берутся из таблицы ШАГИ в прогон.py.

Главное свойство: скрипт не делает вид, что понял всё. Имя файла может приходить
в open() параметром функции — такие случаи он развернуть не может и честно кладёт
их в отдельную колонку «упоминает», а не записывает файл в непрочитанные. Вывод
«этот файл не читает никто» имеет цену только при таком поведении.

Скрипт ничего не меняет и никуда не пишет, кроме stdout.
"""
import sys, os, ast, importlib.util
from collections import defaultdict

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)
ЭТОТ_ФАЙЛ = os.path.basename(os.path.abspath(__file__))
ИНСТРУМЕНТЫ = {ЭТОТ_ФАЙЛ, "сравнить_разбор.py"}   # не шаги конвейера
ДАННЫЕ = (".json", ".jsonl", ".txt", ".md", ".xlsx", ".csv")


def похоже_на_имя(v):
    """Литерал — это имя одного файла, а не фраза про файлы. Строка вида
    «04_карта.json + 11_проверка.json» встречается в описании шага и именем файла
    не является."""
    return (v.endswith(ДАННЫЕ) and len(v) < 120
            and not any(c in v for c in " \n\t+,"))


def литералы(узел):
    """Строковые литералы, похожие на имя файла данных, внутри выражения."""
    out = []
    for n in ast.walk(узел):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            v = n.value
            if похоже_на_имя(v):
                out.append(v)
    return out


def режим(вызов):
    """Второй позиционный аргумент open() или mode=..., по умолчанию чтение."""
    if len(вызов.args) > 1 and isinstance(вызов.args[1], ast.Constant):
        return str(вызов.args[1].value)
    for kw in вызов.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return "r"


def переменные(узлы):
    """имя переменной → имена файлов, если она присвоена выражением с литералом.
    Покрывает `путь = os.path.join(папка, "02_чанки.jsonl")` и константы модуля.
    `узлы` — область видимости: тело функции или тело модуля без функций.
    Раньше карта была одна на файл, и `п` из разных функций сливались:
    `писать()` числился писателем всего, что где-то присваивали в `п`."""
    карта = defaultdict(set)
    for узел in узлы:
        if isinstance(узел, ast.Assign):
            имена = литералы(узел.value)
            if имена:
                for цель in узел.targets:
                    if isinstance(цель, ast.Name):
                        карта[цель.id].update(имена)
    return карта


def _области(дерево):
    """[(узлы области, карта переменных)]: модуль без тел функций и каждая функция."""
    функции = [ф for ф in ast.walk(дерево) if isinstance(ф, ast.FunctionDef)]
    внутри = {id(n) for ф in функции for n in ast.walk(ф)}
    модуль = [n for n in ast.walk(дерево) if id(n) not in внутри]
    общая = переменные(модуль)
    области = [(модуль, общая)]
    for ф in функции:
        своя = переменные(list(ast.walk(ф)))
        for к, v in общая.items():
            своя.setdefault(к, set()).update(v)
        # узлы функции без вложенных функций
        вложенные = {id(n) for г in ast.walk(ф) if isinstance(г, ast.FunctionDef) and г is not ф
                     for n in ast.walk(г)}
        области.append(([n for n in ast.walk(ф) if id(n) not in вложенные], своя))
    return области


def _обёртки(дерево):
    """Функции-обёртки над open(): {имя функции: режим}, где параметр функции
    попадает в путь open(). `читать(папка, имя)` — самая частая форма в проекте:
    без этого шага половина чтений числилась «упоминанием»."""
    обёртки = {}
    кандидаты = [(ф.name, ф) for ф in ast.walk(дерево) if isinstance(ф, ast.FunctionDef)]
    # `ч = lambda f: json.load(open(os.path.join(папка, f)))` — та же обёртка.
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Assign) and isinstance(узел.value, ast.Lambda):
            for ц in узел.targets:
                if isinstance(ц, ast.Name):
                    кандидаты.append((ц.id, узел.value))
    for имя_ф, ф in кандидаты:
        параметры = {а.arg for а in ф.args.args}
        # Локальные имена, выведенные из параметров: `п = os.path.join(папка, имя)`.
        for _ in range(2):
            for узел in ast.walk(ф):
                if isinstance(узел, ast.Assign) and any(
                        isinstance(n, ast.Name) and n.id in параметры for n in ast.walk(узел.value)):
                    параметры |= {ц.id for ц in узел.targets if isinstance(ц, ast.Name)}
        for узел in ast.walk(ф):
            if not (isinstance(узел, ast.Call) and isinstance(узел.func, ast.Name)
                    and узел.func.id == "open" and узел.args):
                continue
            имена_в_пути = {n.id for n in ast.walk(узел.args[0]) if isinstance(n, ast.Name)}
            if имена_в_пути & параметры:
                р = режим(узел)
                обёртки[имя_ф] = "w" if any(c in р for c in "wax") else "r"
    return обёртки


def разобрать(путь):
    """(читает, пишет, упоминает) — множества имён файлов.

    Чтением считается open() с литералом в пути, open() переменной, присвоенной
    из литерала, и вызов функции-обёртки над open() с литералом в аргументах.
    «упоминает» — литералы, не привязанные ни к чему из этого."""
    дерево = ast.parse(open(путь, encoding="utf-8").read(), filename=путь)
    обёртки = _обёртки(дерево)
    читает, пишет, все_литералы = set(), set(), set()

    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Constant) and isinstance(узел.value, str):
            v = узел.value
            if похоже_на_имя(v):
                все_литералы.add(v)

    for узлы, перем in _области(дерево):
        for узел in узлы:
            if not (isinstance(узел, ast.Call) and узел.args):
                continue
            if isinstance(узел.func, ast.Name) and узел.func.id == "open":
                имена = set(литералы(узел.args[0]))
                if not имена:                       # open(путь) — разворачиваем переменную
                    for n in ast.walk(узел.args[0]):
                        if isinstance(n, ast.Name) and n.id in перем:
                            имена |= перем[n.id]
                (пишет if any(c in режим(узел) for c in "wax") else читает).update(имена)
            elif isinstance(узел.func, ast.Name) and узел.func.id in обёртки:
                имена = {и for а in узел.args for и in литералы(а)}
                (пишет if обёртки[узел.func.id] == "w" else читает).update(имена)

    упоминает = все_литералы - читает - пишет
    return читает, пишет, упоминает


def _шаги():
    сп = importlib.util.spec_from_file_location("шаги", os.path.join(ЗДЕСЬ, "шаги.py"))
    м = importlib.util.module_from_spec(сп); сп.loader.exec_module(м)
    return м


def модельные_шаги():
    """Шаги модели из объявления `шаги.py`."""
    ш = _шаги()
    return [(с["код"], с["чем"], ш.файлы_входа(с), с["выходы"]) for с in ш.модельные()]


def сверить_с_объявлением(разборы):
    """Д-6: скрипт читает только объявленные входы и свои выходы, пишет только
    объявленные выходы. `разборы` — {скрипт: (читает, пишет)} по коду.
    Объявление в `шаги.py` — правда; расхождение — нарушение, а не заметка."""
    ш = _шаги()
    нарушения = []
    по_скрипту = {}
    for с in ш.скриптовые():
        имя = с["чем"].split()[0]
        вх, вых = по_скрипту.setdefault(имя, (set(), set()))
        вх.update(ш.файлы_входа(с))
        вых.update(с["выходы"])
        вых.update(с["выгружает"])
    for имя, (объявлено_читает, объявлено_пишет) in по_скрипту.items():
        if имя not in разборы:
            continue
        читает, пишет = разборы[имя]
        лишнее = sorted(читает - объявлено_читает - объявлено_пишет)
        if лишнее:
            нарушения.append(f"{имя} читает {', '.join(лишнее)} — в объявлении шага "
                             f"этого входа нет (Д-6: читать можно только объявленное)")
        мимо = sorted(пишет - объявлено_пишет - {ш.ОТПЕЧАТКИ, ш.ВЫЗОВ})
        if мимо:
            нарушения.append(f"{имя} пишет {', '.join(мимо)} — в объявлении шага "
                             f"этого выхода нет (Д-2: писатель обязан быть объявлен)")
    return нарушения


def колонка(словарь, ключ):
    return ", ".join(sorted(словарь.get(ключ, []))) or "—"


def main(папка=ЗДЕСЬ):
    скрипты = sorted(f for f in os.listdir(папка)
                     if f.endswith(".py") and f not in ИНСТРУМЕНТЫ)
    пишут, читают, упоминают = defaultdict(list), defaultdict(list), defaultdict(list)

    print("# Карта файловых зависимостей\n")
    print("Построена разбором кода, а не по памяти. Колонка «упоминает» — файлы, чьё "
          "имя встречается в скрипте, но привязать его к open() автоматически не "
          "удалось (имя уходит параметром в обёртку). Это не значит, что файл не "
          "читается: значит, что здесь машина не берётся утверждать.\n")

    print("## Скрипты\n")
    разборы = {}
    for s in скрипты:
        try:
            ч, п, у = разобрать(os.path.join(папка, s))
        except SyntaxError as e:
            print(f"**{s}** — не разбирается: {e}\n")
            continue
        разборы[s] = (ч, п)
        for f in ч:
            читают[f].append(s)
        for f in п:
            пишут[f].append(s)
        for f in у:
            упоминают[f].append(s)
        print(f"**{s}**")
        print(f"  читает:    {', '.join(sorted(ч)) or '—'}")
        print(f"  пишет:     {', '.join(sorted(п)) or '—'}")
        if у:
            print(f"  упоминает: {', '.join(sorted(у))}")
        print()

    шаги = модельные_шаги()
    if шаги:
        print("## Шаги модели (из объявления шаги.py)\n")
        for шаг, промт, вход, выход in шаги:
            print(f"**{шаг} · {промт}**")
            print(f"  вход:  {', '.join(вход)}")
            print(f"  выход: {', '.join(выход)}\n")
            читают[промт].append(f"{шаг}")
            for f in выход:
                пишут[f].append(f"{шаг} ({промт})")
            for f in вход:
                читают[f].append(f"{шаг} ({промт})")

    print("## Кто что пишет и кто это читает\n")
    print("| файл | пишет | читает | упоминает |")
    print("|---|---|---|---|")
    for f in sorted(set(пишут) | set(читают) | set(упоминают)):
        print(f"| `{f}` | {колонка(пишут, f)} | {колонка(читают, f)} | {колонка(упоминают, f)} |")

    тупики = sorted(f for f in пишут if f not in читают and f not in упоминают)
    ничьи = sorted(f for f in читают if f not in пишут)
    print("\n## На что посмотреть\n")
    print("**Пишется, и никто его не читает и даже не упоминает** — тупик либо выход "
          "наружу, для человека:")
    print("  " + (", ".join(f"`{f}`" for f in тупики) or "— нет"))
    print("\n**Читается, но никем не пишется** — внешний вход либо опечатка в имени:")
    print("  " + (", ".join(f"`{f}`" for f in ничьи) or "— нет"))

    в_графе = set(пишут) | set(читают) | set(упоминают)
    лишние = []
    for под in ("_канон", "_промты"):
        d = os.path.join(КОРЕНЬ, под)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(ДАННЫЕ) and f not in в_графе:
                лишние.append(f"{под}/{f}")
    print("\n**Канон и промты, которых нет в графе** — их не открывает ни один шаг:")
    print("  " + (", ".join(f"`{f}`" for f in лишние) or "— нет"))

    нарушения = сверить_с_объявлением(разборы)
    print("\n## Код против объявления шагов\n")
    if нарушения:
        for н in нарушения:
            print(f"  ✗ {н}")
        return 1
    print("  каждый скриптовый шаг читает только объявленные входы и пишет только объявленные выходы")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ЗДЕСЬ))
