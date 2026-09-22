# -*- coding: utf-8 -*-
"""Прогон всех PDF из корпуса исходников, по одному материалу.

  python3 _скрипты/прогон_корпус.py

Папка материала: канал_slug от имени PDF (NFC). Старых исключений нет.
Уже дошедшие до конца (отбор.md и реестр.json) пропускаются.
Отказ одного материала не останавливает очередь.
"""
import os, re, subprocess, sys, unicodedata

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)
sys.path.insert(0, ЗДЕСЬ)
import общее


def _slug(имя):
    s = os.path.splitext(имя)[0]
    s = unicodedata.normalize("NFC", s).strip()
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    return s.strip("_")[:72] or "материал"


def очередь():
    корпус = общее.корень_корпуса("прогон_корпус")
    пары, занято = [], set()
    for канал in sorted(os.listdir(корпус)):
        папка = os.path.join(корпус, канал)
        if not os.path.isdir(папка):
            continue
        for имя in sorted(os.listdir(папка)):
            if имя.startswith(".") or not имя.lower().endswith(".pdf"):
                continue
            отн = unicodedata.normalize("NFC", f"{канал}/{имя}")
            метка = f"{канал}_{_slug(имя)}"
            if метка in занято:
                raise SystemExit(f"прогон_корпус: два исходника претендуют на {метка}")
            занято.add(метка)
            пары.append((отн, os.path.join(КОРЕНЬ, "материалы", метка)))
    if not пары:
        raise SystemExit("прогон_корпус: в корпусе нет PDF")
    return пары


def готов(папка):
    return all(os.path.isfile(os.path.join(папка, ф))
               for ф in ("отбор.md", "реестр.json"))


def main():
    пары = очередь()
    print(f"корпус: {len(пары)} исходников")
    коды = []
    for i, (отн, папка) in enumerate(пары, 1):
        метка = os.path.basename(папка)
        if готов(папка):
            print(f"· {i}/{len(пары)} {метка} — уже до конца")
            коды.append(0)
            continue
        print(f"\n======== {i}/{len(пары)} {метка} ========\n  {отн}")
        код = subprocess.call(
            [sys.executable, os.path.join(ЗДЕСЬ, "прогон.py"), отн, папка],
            cwd=КОРЕНЬ)
        print(f"EXIT {метка} {код}")
        коды.append(код)
    отказ = sum(1 for к in коды if к)
    print(f"\nкорпус: готово {len(коды) - отказ}/{len(коды)}, отказов {отказ}")
    return 1 if отказ else 0


if __name__ == "__main__":
    raise SystemExit(main())
