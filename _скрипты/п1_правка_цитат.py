# -*- coding: utf-8 -*-
"""Точечная правка цитат П1: свой ответ + брак B4, не весь шаг заново.

  python3 _скрипты/п1_правка_цитат.py материалы/<папка>
"""
import json, os, sys, importlib.util

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)
ПРОМТ = os.path.join(КОРЕНЬ, "_промты", "П1_правка_цитат.md")


СПИСКИ_С_ЦИТАТОЙ = ("кейсы", "цифры", "инструменты", "опоры_под_практику")


def убрать_пустые_цитаты(объект):
    """Строка списка без дословной цитаты — не ответ, а дыра в контракте П1."""
    if not isinstance(объект, dict):
        return объект
    for ключ in СПИСКИ_С_ЦИТАТОЙ:
        ряды = объект.get(ключ)
        if not isinstance(ряды, list):
            continue
        объект[ключ] = [э for э in ряды
                        if isinstance(э, dict) and str(э.get("цитата") or "").strip()]
    return объект


def _модуль(имя, файл):
    сп = importlib.util.spec_from_file_location(имя, os.path.join(ЗДЕСЬ, файл))
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    return м


def main(папка):
    модель = _модуль("модель", "модель.py")
    if not модель.включен():
        print("п1_правка_цитат: нет API_KEY")
        return 1
    проверка = os.path.join(папка, "03_проверка.json")
    выжимки_п = os.path.join(папка, "03_выжимки.jsonl")
    чанки_п = os.path.join(папка, "02_чанки.jsonl")
    if not all(os.path.isfile(п) for п in (выжимки_п, чанки_п, ПРОМТ)):
        print("п1_правка_цитат: нет выжимок, чанков или промта")
        return 1
    if not os.path.isfile(проверка):
        print("п1_правка_цитат: отчёт B4 снят после отказа — пересчитываю проверку")
        b4 = _модуль("b4", "b4_проверка_выжимок.py")
        b4.main(папка)
        if not os.path.isfile(проверка):
            print("п1_правка_цитат: проверка так и не записалась")
            return 1
    брак = json.load(open(проверка, encoding="utf-8")).get("брак") or []
    брак = [б for б in брак if б.get("цитата") and б.get("чанк")]
    if not брак:
        print("п1_правка_цитат: в проверке нет бракованных цитат")
        return 1
    выжимки = [json.loads(л) for л in open(выжимки_п, encoding="utf-8") if л.strip()]
    по_id = {в.get("чанк_id"): в for в in выжимки}
    чанки = {c["id"]: c for c in
             (json.loads(л) for л in open(чанки_п, encoding="utf-8") if л.strip())}
    промт = open(ПРОМТ, encoding="utf-8").read().strip()
    по_чанку = {}
    for б in брак:
        по_чанку.setdefault(б["чанк"], []).append(б)
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    n = len(по_чанку)
    for i, (ид, строки) in enumerate(по_чанку.items(), 1):
        было = по_id.get(ид)
        чанк = чанки.get(ид)
        if not было or not чанк:
            print(f"  · {ид}: нет выжимки или чанка — пропуск")
            continue
        print(f"    API П1_правка_цитат.md: {i}/{n} {ид} цитат={len(строки)}")
        user = "\n".join([
            "## Фрагмент (02_чанки)",
            "```json",
            json.dumps(чанк, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Твой прежний ответ",
            "```json",
            json.dumps(было, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Брак скрипта (эти цитаты не найдены)",
            "```json",
            json.dumps(строки, ensure_ascii=False, indent=2),
            "```",
            "",
            "Верни один JSON-объект выжимки. Исправь только цитаты из брака.",
        ])
        объект, u = модель.спросить(
            [{"role": "system", "content": промт},
             {"role": "user", "content": user}],
            effort="medium")
        usage["prompt_tokens"] += int((u or {}).get("prompt_tokens") or 0)
        usage["completion_tokens"] += int((u or {}).get("completion_tokens") or 0)
        if not isinstance(объект, dict) or объект.get("чанк_id") != ид:
            print(f"  · {ид}: ответ без того же чанк_id — оставляю как было")
            continue
        по_id[ид] = убрать_пустые_цитаты(объект)
    with open(выжимки_п, "w", encoding="utf-8") as f:
        for в in выжимки:
            ид = в.get("чанк_id")
            f.write(json.dumps(по_id.get(ид, в), ensure_ascii=False) + "\n")
    print(f"п1_правка_цитат: чанков {n}, токены вход {usage['prompt_tokens']}, "
          f"выход {usage['completion_tokens']}")
    return 0


def только_пустые(папка):
    выжимки_п = os.path.join(папка, "03_выжимки.jsonl")
    if not os.path.isfile(выжимки_п):
        print("п1_правка_цитат: нет выжимок")
        return 1
    строки, n = [], 0
    for л in open(выжимки_п, encoding="utf-8"):
        if not л.strip():
            continue
        в = json.loads(л)
        было = json.dumps(в, ensure_ascii=False)
        убрать_пустые_цитаты(в)
        if json.dumps(в, ensure_ascii=False) != было:
            n += 1
        строки.append(в)
    with open(выжимки_п, "w", encoding="utf-8") as f:
        for в in строки:
            f.write(json.dumps(в, ensure_ascii=False) + "\n")
    print(f"п1_правка_цитат: снято пустых цитат в {n} чанках")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[2] == "--убрать-пустые":
        raise SystemExit(только_пустые(sys.argv[1]))
    if len(sys.argv) != 2:
        raise SystemExit("python3 _скрипты/п1_правка_цитат.py материалы/<папка>")
    raise SystemExit(main(sys.argv[1]))
