# -*- coding: utf-8 -*-
"""Один материал до отбор.md. Отказ — в ошибки_прогона.txt.

Один проход. Отказ — в журнал, ответ модели на диске не трогаем: правку
делает арбитраж, затем снова `довести`. Автоповтора модели нет.

  python3 _скрипты/прогон_последовательно.py
"""
import json, os, re, subprocess, sys
from datetime import datetime

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)
sys.path.insert(0, ЗДЕСЬ)
import прогон_корпус

ЖУРНАЛ = os.path.join(КОРЕНЬ, "ошибки_прогона.txt")
МАКС_ПОВТОРОВ = 1

СНЯТЬ_ПО_ШАГУ = {
    "b4_проверка_выжимок.py": "03_выжимки.jsonl",
    "П1_выжимка_чанка.md": "03_выжимки.jsonl",
    "b4т_проверка_тем.py": "03_темы.jsonl",
    "П1т_темы_чанка.md": "03_темы.jsonl",
    "И1_опознание.md": "00_опознание.json",
    "о_источник.py": "00_опознание.json",
    "И2_строка_справочника.md": "00_справочник_строка.json",
    "И3_строка_автора.md": "00_авторы.jsonl",
    "авторы.py": "00_авторы.jsonl",      # останавливается «авторы.py записать»
    "П2_карта_материала.md": "04_решение.json",
    "b5_карта.py": "04_решение.json",
    "П3_исключения_тем.md": "10_исключения.json",
    "П2т_сюжеты_темы.md": "10_сюжеты.jsonl",
    "П4_строгая_проверка.md": "11_проверка.json",
    "П5_скоринг.md": "12_скоринг.json",
    "o4_скоринг.py": "11_проверка.json",
    "У1_уровень_заготовки.md": "00_уровень.jsonl",
    "о_уровень.py": "00_уровень.jsonl",
    "b5_агрегат.py": "04_агрегат.json",
}

# После точечной правки ответа проверка должна пойти заново.
# Иначе отчёт с отказом остаётся на диске, и прогон.py считает шаг сделанным.
СНЯТЬ_ПРОВЕРКУ_ПОСЛЕ_ПРАВКИ = {
    "П1": "03_проверка.json",
    "П1-пусто": "03_проверка.json",
    "П1т": "03_проверка_тем.json",
    "П1т-отрезки": "03_проверка_тем.json",
    "П1т-адреса": "03_проверка_тем.json",
}


def журнал(текст):
    os.makedirs(КОРЕНЬ, exist_ok=True)
    with open(ЖУРНАЛ, "a", encoding="utf-8") as f:
        f.write(текст.rstrip() + "\n")
    print(текст.rstrip(), flush=True)


def шапка():
    if os.path.isfile(ЖУРНАЛ) and os.path.getsize(ЖУРНАЛ):
        return
    журнал(
        "ошибки прогона пайплайна отбора\n"
        "каждый отказ: материал, шаг, код, детали. промты не меняем.\n"
        f"старт журнала: {datetime.now().isoformat(timespec='seconds')}\n"
    )


def детали(лог):
    строки = []
    for л in лог.splitlines():
        s = л.strip()
        if (s.startswith("✗") or s.startswith("■") or s.startswith("!")
                or "вызов API не удался" in s or "код 4:" in s
                or "не по контракту" in s or "получен на другой вход" in s):
            строки.append(л.rstrip())
    return "\n".join(строки[-40:]) or лог[-2000:]


def последний_стоп(лог):
    """Имя файла шага из последней строки «■ … остановился»."""
    шаг = None
    for л in лог.splitlines():
        if "■" not in л or "остановился" not in л:
            continue
        for кусок in л.split():
            if кусок.endswith(".py") or кусок.endswith(".md"):
                шаг = кусок
    return шаг


def _звать(скрипт, папка):
    return subprocess.call(
        [sys.executable, "-u", os.path.join(ЗДЕСЬ, скрипт), папка],
        cwd=КОРЕНЬ) == 0


def _правка_пары_отрезков(папка):
    """П1т иногда даёт `[6]` вместо `[6, 6]` — это тот же отрезок, не новый смысл."""
    путь = os.path.join(папка, "03_темы.jsonl")
    if not os.path.isfile(путь):
        журнал("  правка П1т-отрезки: нет 03_темы.jsonl")
        return False
    строки = []
    правка = 0
    for л in open(путь, encoding="utf-8"):
        if not л.strip():
            continue
        р = json.loads(л)
        for т in р.get("темы") or []:
            for б in т.get("блоки") or []:
                о = б.get("отрезки")
                if isinstance(о, int) and not isinstance(о, bool):
                    б["отрезки"] = [о, о]
                    правка += 1
                elif (isinstance(о, list) and len(о) == 1
                      and isinstance(о[0], int) and not isinstance(о[0], bool)):
                    б["отрезки"] = [о[0], о[0]]
                    правка += 1
        строки.append(json.dumps(р, ensure_ascii=False))
    if not правка:
        return False
    with open(путь, "w", encoding="utf-8") as f:
        f.write("\n".join(строки) + "\n")
    журнал(f"  правка П1т-отрезки: {правка} адресов [n] → [n, n]")
    return True


def правка_цитат(лог, папка):
    """Код 4 из-за цитат: починить ответ упавшего шага, не писать его заново."""
    шаг = последний_стоп(лог)
    if шаг == "b4_проверка_выжимок.py" and "недословные цитаты" in лог:
        if not os.path.isfile(os.path.join(папка, "03_выжимки.jsonl")):
            журнал("  правка П1: нет 03_выжимки.jsonl")
            return False
        if _звать("п1_правка_цитат.py", папка):
            return "П1"
        журнал("  правка П1 не записала выжимки")
        return False
    if (шаг == "b4_проверка_выжимок.py" and "цитата" in лог
            and ("поле есть, но пустое" in лог or "нет вовсе" in лог)):
        if not os.path.isfile(os.path.join(папка, "03_выжимки.jsonl")):
            журнал("  правка П1: нет 03_выжимки.jsonl")
            return False
        код = subprocess.call(
            [sys.executable, "-u", os.path.join(ЗДЕСЬ, "п1_правка_цитат.py"),
             папка, "--убрать-пустые"],
            cwd=КОРЕНЬ)
        if код == 0:
            return "П1-пусто"
        журнал("  правка П1-пусто не записала выжимки")
        return False
    if шаг == "b4т_проверка_тем.py":
        какие = []
        if "не пара номеров" in лог and _правка_пары_отрезков(папка):
            какие.append("П1т-отрезки")
        # Адрес блока чинится из позиции его цитаты, без модели: перевызов П1т
        # на этой ошибке не сходится (см. п1т_правка_адресов).
        if ("не внутри фрагментов темы" in лог or "вне отрезков" in лог):
            if _звать("п1т_правка_адресов.py", папка):
                какие.append("П1т-адреса")
        if "недословна" in лог or "цитата пуста" in лог:
            if not os.path.isfile(os.path.join(папка, "03_темы.jsonl")):
                журнал("  правка П1т: нет 03_темы.jsonl")
                return False
            if _звать("п1т_правка_цитат.py", папка):
                какие.append("П1т")
            elif not какие:
                журнал("  правка П1т не записала темы")
                return False
        if какие:
            return "+".join(какие)
    if шаг == "o4_скоринг.py" and "цитируют не карту" in лог:
        if not os.path.isfile(os.path.join(папка, "11_проверка.json")):
            журнал("  правка П4: нет 11_проверка.json")
            return False
        if _звать("п4_правка_цитат.py", папка):
            return "П4"
        журнал("  правка П4 не записала проверку")
        return False
    if шаг == "о_уровень.py" and "цитирует не заготовку" in лог:
        if not os.path.isfile(os.path.join(папка, "00_уровень.jsonl")):
            журнал("  правка У1: нет 00_уровень.jsonl")
            return False
        if _звать("у1_правка_цитат.py", папка):
            return "У1"
        журнал("  правка У1 не записала уровни")
        return False
    return False


def файл_снять(лог):
    шаг = последний_стоп(лог)
    if шаг and шаг in СНЯТЬ_ПО_ШАГУ:
        return СНЯТЬ_ПО_ШАГУ[шаг]
    m = re.search(r"удалите (\S+)", лог)
    if m:
        return os.path.basename(m.group(1).rstrip(").,"))
    return None


def прогон(отн, папка):
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(ЗДЕСЬ, "прогон.py"), отн, папка],
        cwd=КОРЕНЬ, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        bufsize=1)
    части = []
    for строка in proc.stdout:
        sys.stdout.write(строка)
        sys.stdout.flush()
        части.append(строка)
    код = proc.wait()
    return код, "".join(части)


def довести(i, всего, отн, папка):
    метка = os.path.basename(папка)
    if прогон_корпус.готов(папка):
        print(f"· {i}/{всего} {метка} — уже до конца")
        return 0
    журнал(f"\n======== {i}/{всего} {метка} ========\n  {отн}")
    код, лог = прогон(отн, папка)
    if код == 0:
        журнал("  готово, попытка 1")
        return 0
    журнал(
        f"  отказ {datetime.now().isoformat(timespec='seconds')}"
        f" попытка 1/{МАКС_ПОВТОРОВ} код {код}\n"
        f"{детали(лог)}\n"
        f"  стоп: {метка} — нужна правка ответа (автоповтора нет)"
    )
    return 1


def main():
    шапка()
    пары = прогон_корпус.очередь()
    print(f"последовательно: {len(пары)} исходников, журнал {ЖУРНАЛ}")
    for i, (отн, папка) in enumerate(пары, 1):
        if довести(i, len(пары), отн, папка):
            return 1
    журнал(f"\nкорпус: все доведены {datetime.now().isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
