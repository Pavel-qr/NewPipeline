# -*- coding: utf-8 -*-
"""
Окружение: какие внешние библиотеки нужны пайплайну и есть ли они.

  python3 _скрипты/окружение.py     — проверить, код 0/1

Единственный список зависимостей — `requirements.txt` в корне проекта; здесь
записано только, под каким именем каждый пакет импортируется (у `python-docx`
имя пакета не совпадает с именем модуля). Скрипт, которому нужна библиотека,
зовёт `требовать("docx")` и получает внятный отказ с командой установки вместо
трассировки `ModuleNotFoundError`. `запуск.py` зовёт
`проверить()` первым: раньше он разбирал только синтаксис, и `import openpyxl`
внутри функции для него был способом удовлетворить проверку, а не её предметом.
"""
import os, sys, importlib

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)
ТРЕБОВАНИЯ = os.path.join(КОРЕНЬ, "requirements.txt")
МИН_PYTHON = (3, 8)

# пакет в requirements.txt → модуль, который импортируется
МОДУЛЬ = {"pymupdf": "pymupdf", "pymupdf4llm": "pymupdf4llm",
          "python-docx": "docx", "openpyxl": "openpyxl", "certifi": "certifi"}


def пакеты():
    """Имена пакетов из requirements.txt, без версий и комментариев."""
    if not os.path.exists(ТРЕБОВАНИЯ):
        raise SystemExit(f"окружение: нет {ТРЕБОВАНИЯ}")
    имена = []
    for строка in open(ТРЕБОВАНИЯ, encoding="utf-8"):
        строка = строка.split("#")[0].strip()
        if строка:
            имена.append(строка.split(">=")[0].split("==")[0].strip())
    return имена


def требовать(модуль, кто="скрипт"):
    """Импорт с внятным отказом: имя модуля, пакет для pip, команда установки."""
    try:
        return importlib.import_module(модуль)
    except ImportError:
        пакет = next((п for п, м in МОДУЛЬ.items() if м == модуль), модуль)
        raise SystemExit(f"{кто}: нет библиотеки «{модуль}» (пакет {пакет}). "
                         f"Установка: python3 -m pip install -r requirements.txt")


def проверить():
    """Список отказов: версия Python и каждый пакет из requirements.txt."""
    отказы = []
    if sys.version_info < МИН_PYTHON:
        отказы.append(f"Python {sys.version.split()[0]}, нужен ≥ {'.'.join(map(str, МИН_PYTHON))}")
    for пакет in пакеты():
        модуль = МОДУЛЬ.get(пакет)
        if модуль is None:
            отказы.append(f"пакет «{пакет}» есть в requirements.txt, но окружение.МОДУЛЬ не "
                          f"знает, как он импортируется — дополните карту")
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
        print("  установка: python3 -m pip install -r requirements.txt")
        raise SystemExit(1)
    print(f"окружение в порядке: Python {sys.version.split()[0]}, "
          f"пакеты {', '.join(пакеты())}")
    raise SystemExit(0)
