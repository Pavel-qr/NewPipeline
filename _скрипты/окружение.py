# -*- coding: utf-8 -*-
"""
Окружение: какие внешние библиотеки нужны пайплайну и есть ли они.

  python3 _скрипты/окружение.py     — проверить, код 0/1

Единственный список зависимостей — `[project]` в `pyproject.toml`; оттуда же
берётся и минимальная версия Python (`requires-python`). Здесь записано только,
под каким именем каждый пакет импортируется (у `python-docx` имя пакета не
совпадает с именем модуля). Скрипт, которому нужна библиотека, зовёт
`требовать("docx")` и получает внятный отказ с командой установки вместо
трассировки `ModuleNotFoundError`. `запуск.py` зовёт `проверить()` первым:
раньше он разбирал только синтаксис, и `import openpyxl` внутри функции для
него был способом удовлетворить проверку, а не её предметом.

До 22 сентября список лежал в `requirements.txt`. Файл убран, зависимостями
ведает uv по `pyproject.toml` — читаем оттуда, чтобы мнение о составе
окружения осталось одно.
"""
import os, re, sys, importlib, tomllib

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)
ПРОЕКТ = os.path.join(КОРЕНЬ, "pyproject.toml")
УСТАНОВКА = "uv sync"

# пакет в pyproject → модуль, который импортируется
МОДУЛЬ = {"pymupdf": "pymupdf", "pymupdf4llm": "pymupdf4llm",
          "python-docx": "docx", "openpyxl": "openpyxl", "certifi": "certifi"}


def _проект():
    if not os.path.exists(ПРОЕКТ):
        raise SystemExit(f"окружение: нет {ПРОЕКТ}")
    with open(ПРОЕКТ, "rb") as f:
        return tomllib.load(f).get("project") or {}


def пакеты():
    """Имена пакетов из [project].dependencies, без версий, extras и маркеров."""
    имена = []
    for строка in _проект().get("dependencies") or []:
        имя = re.split(r"[<>=!~;\[\s]", строка.strip(), maxsplit=1)[0]
        if имя:
            имена.append(имя)
    return имена


def мин_python():
    """(3, 14) из `requires-python = ">=3.14"`. Не указано — не проверяем."""
    требование = (_проект().get("requires-python") or "").strip()
    m = re.search(r">=\s*(\d+)\.(\d+)", требование)
    return (int(m.group(1)), int(m.group(2))) if m else None


def требовать(модуль, кто="скрипт"):
    """Импорт с внятным отказом: имя модуля, пакет, команда установки."""
    try:
        return importlib.import_module(модуль)
    except ImportError:
        пакет = next((п for п, м in МОДУЛЬ.items() if м == модуль), модуль)
        raise SystemExit(f"{кто}: нет библиотеки «{модуль}» (пакет {пакет}). "
                         f"Установка: {УСТАНОВКА}")


def проверить():
    """Список отказов: версия Python и каждый пакет из pyproject.toml."""
    отказы = []
    нужен = мин_python()
    if нужен and sys.version_info < нужен:
        отказы.append(f"Python {sys.version.split()[0]}, "
                      f"нужен ≥ {'.'.join(map(str, нужен))}")
    for пакет in пакеты():
        модуль = МОДУЛЬ.get(пакет)
        if модуль is None:
            отказы.append(f"пакет «{пакет}» есть в pyproject.toml, но окружение.МОДУЛЬ "
                          f"не знает, как он импортируется — дополните карту")
            continue
        try:
            importlib.import_module(модуль)
        except ImportError:
            отказы.append(f"нет «{модуль}» (пакет {пакет})")
    return отказы


if __name__ == "__main__":
    о = проверить()
    if о:
        print("ОКРУЖЕНИЕ НЕПОЛНО:")
        for x in о:
            print("  ✗ " + x)
        print(f"  установка: {УСТАНОВКА}")
        raise SystemExit(1)
    print(f"окружение в порядке: Python {sys.version.split()[0]}, "
          f"пакеты {', '.join(пакеты())}")
    raise SystemExit(0)
