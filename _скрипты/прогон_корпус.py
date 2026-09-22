# -*- coding: utf-8 -*-
"""Прогон всех PDF из корпуса исходников, по 10 материалов одновременно.

  python3 _скрипты/прогон_корпус.py
  python3 _скрипты/прогон_корпус.py --потоков 1      # старое поведение, по одному

Папка материала: канал_slug от имени PDF (NFC). Старых исключений нет.
Уже дошедшие до конца (отбор.md и реестр.json) пропускаются.
Отказ одного материала не останавливает очередь.

Материалы независимы: у каждого своя папка, свои файлы и свои вызовы модели.
Общее — только справочники в `_канон/`, и запись туда идёт под замком
(`общее.блокировка` в `авторы.py` и `о_источник.py`).
"""
import io, os, re, subprocess, sys, threading, unicodedata
from concurrent.futures import ThreadPoolExecutor

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)
sys.path.insert(0, ЗДЕСЬ)
import общее

ПОТОКОВ = 10


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


class _ПоПотокам(io.TextIOBase):
    """Подмена sys.stdout на время параллельной очереди: поток, у которого заведён
    буфер, пишет в него, остальное идёт на экран как обычно. Без этого строки
    десяти прогонов чередуются и лог нечитаем."""

    def __init__(self, настоящий):
        self.настоящий = настоящий
        self.свой = threading.local()

    def write(self, текст):
        буфер = getattr(self.свой, "буфер", None)
        return (self.настоящий if буфер is None else буфер).write(текст)

    def flush(self):
        if getattr(self.свой, "буфер", None) is None:
            self.настоящий.flush()


def параллельно(пары, работа, потоков=ПОТОКОВ):
    """`работа(отн, папка) → код` по `потоков` материалов сразу; коды — в порядке
    очереди, вывод каждого материала печатается целиком, когда тот закончился."""
    if потоков <= 1:
        return [работа(отн, папка) for отн, папка in пары]
    вывод = _ПоПотокам(sys.stdout)
    печать = threading.Lock()
    сделано = [0]

    def задача(отн, папка):
        вывод.свой.буфер = io.StringIO()
        try:
            return работа(отн, папка)
        except Exception as сбой:
            print(f"■ {os.path.basename(папка)}: {type(сбой).__name__}: {сбой}")
            return общее.ОТКАЗ
        finally:
            текст = вывод.свой.буфер.getvalue().rstrip()
            вывод.свой.буфер = None
            with печать:
                сделано[0] += 1
                вывод.настоящий.write(f"{текст}\n[{сделано[0]}/{len(пары)}]\n\n")
                вывод.настоящий.flush()

    прежний = sys.stdout
    sys.stdout = вывод
    try:
        with ThreadPoolExecutor(max_workers=потоков) as пул:
            задачи = [пул.submit(задача, отн, папка) for отн, папка in пары]
            return [з.result() for з in задачи]
    finally:
        sys.stdout = прежний


def один(отн, папка):
    метка = os.path.basename(папка)
    if готов(папка):
        print(f"· {метка} — уже до конца")
        return 0
    print(f"======== {метка} ========\n  {отн}")
    # Вывод дочернего прогона забирается трубой, а не наследованием stdout:
    # иначе он пишет в настоящий терминал мимо буфера потока.
    p = subprocess.run(
        [sys.executable, "-u", os.path.join(ЗДЕСЬ, "прогон.py"), отн, папка],
        cwd=КОРЕНЬ, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(p.stdout.rstrip())
    print(f"EXIT {метка} {p.returncode}")
    return p.returncode


def main(потоков=ПОТОКОВ):
    пары = очередь()
    print(f"корпус: {len(пары)} исходников, одновременно {потоков}")
    коды = параллельно(пары, один, потоков)
    отказ = sum(1 for к in коды if к)
    print(f"\nкорпус: готово {len(коды) - отказ}/{len(коды)}, отказов {отказ}")
    return 1 if отказ else 0


def сколько_потоков(argv, умолчание=ПОТОКОВ):
    """`--потоков N` из аргументов; возвращает (N, остальные аргументы)."""
    if "--потоков" in argv:
        i = argv.index("--потоков")
        if i + 1 >= len(argv):
            raise SystemExit("--потоков: после ключа нужно число")
        return max(1, int(argv[i + 1])), argv[:i] + argv[i + 2:]
    return умолчание, list(argv)


def самопроверка():
    порядок = []
    пары = [(f"канал/{i}.pdf", f"материалы/м{i}") for i in range(6)]

    def работа(отн, папка):
        print(f"строка A {папка}")
        порядок.append(папка)
        print(f"строка B {папка}")
        return 0 if папка.endswith(("0", "2", "4")) else 7

    буфер = io.StringIO()
    настоящий, sys.stdout = sys.stdout, буфер
    try:
        коды = параллельно(пары, работа, потоков=3)
    finally:
        sys.stdout = настоящий
    assert коды == [0, 7, 0, 7, 0, 7], коды          # коды в порядке очереди
    assert len(порядок) == 6
    текст = буфер.getvalue()
    for _, папка in пары:                            # вывод материала не разорван
        assert f"строка A {папка}\nстрока B {папка}\n" in текст, текст
    assert параллельно(пары, работа, потоков=1) == [0, 7, 0, 7, 0, 7]
    print("параллельно: коды в порядке очереди, вывод материалов не перемешан")
    return 0


if __name__ == "__main__":
    if "--самопроверка" in sys.argv:
        raise SystemExit(самопроверка())
    потоков, _ = сколько_потоков(sys.argv[1:])
    raise SystemExit(main(потоков))
