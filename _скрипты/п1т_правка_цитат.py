# -*- coding: utf-8 -*-
"""Точечная правка цитат П1т: свой ответ + брак B4т, не весь шаг заново.

  python3 _скрипты/п1т_правка_цитат.py материалы/<папка>
"""
import json, os, sys, importlib.util

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)
ПРОМТ = os.path.join(КОРЕНЬ, "_промты", "П1т_правка_цитат.md")


def _модуль(имя, файл):
    сп = importlib.util.spec_from_file_location(имя, os.path.join(ЗДЕСЬ, файл))
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    return м


def main(папка):
    модель = _модуль("модель", "модель.py")
    if not модель.включен():
        print("п1т_правка_цитат: нет API_KEY")
        return 1
    проверка = os.path.join(папка, "03_проверка_тем.json")
    темы_п = os.path.join(папка, "03_темы.jsonl")
    чанки_п = os.path.join(папка, "02_чанки.jsonl")
    if not all(os.path.isfile(п) for п in (темы_п, чанки_п, ПРОМТ)):
        print("п1т_правка_цитат: нет тем, чанков или промта")
        return 1
    if not os.path.isfile(проверка):
        print("п1т_правка_цитат: отчёт B4т снят после отказа — пересчитываю проверку")
        b4т = _модуль("b4т", "b4т_проверка_тем.py")
        b4т.main(папка)
        if not os.path.isfile(проверка):
            print("п1т_правка_цитат: проверка так и не записалась")
            return 1
    брак = json.load(open(проверка, encoding="utf-8")).get("брак") or []
    брак = [б for б in брак
            if б.get("чанк") and any(к in (б.get("что") or "")
                                     for к in ("недословна", "цитата пуста", "вне отрезков"))]
    if not брак:
        print("п1т_правка_цитат: в проверке нет бракованных цитат")
        return 1
    темы = [json.loads(л) for л in open(темы_п, encoding="utf-8") if л.strip()]
    по_id = {т.get("чанк_id"): т for т in темы}
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
            print(f"  · {ид}: нет тем или чанка — пропуск")
            continue
        print(f"    API П1т_правка_цитат.md: {i}/{n} {ид} цитат={len(строки)}")
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
            "## Брак скрипта (эти цитаты не приняты)",
            "```json",
            json.dumps(строки, ensure_ascii=False, indent=2),
            "```",
            "",
            "Верни один JSON-объект тем фрагмента. Исправь только цитаты из брака.",
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
        по_id[ид] = объект
    with open(темы_п, "w", encoding="utf-8") as f:
        for т in темы:
            ид = т.get("чанк_id")
            f.write(json.dumps(по_id.get(ид, т), ensure_ascii=False) + "\n")
    print(f"п1т_правка_цитат: чанков {n}, токены вход {usage['prompt_tokens']}, "
          f"выход {usage['completion_tokens']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("python3 _скрипты/п1т_правка_цитат.py материалы/<папка>")
    raise SystemExit(main(sys.argv[1]))
