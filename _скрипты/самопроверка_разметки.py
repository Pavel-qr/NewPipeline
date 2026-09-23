# Снятие markdown-разметки Б1: текст обязан уцелеть, разметка — исчезнуть.
# python3 _скрипты/самопроверка_разметки.py
import sys, os
ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ЗДЕСЬ)      # b1 лежит рядом; путей от cwd здесь нет
import b1_нормализация as b1

СЛУЧАИ = [
    # (что даёт pymupdf4llm, что должно остаться)
    ("**Table 4.** Alternative model", "Table 4. Alternative model"),
    ("SRMR<sup>between</sup> = 0.144", "SRMRbetween = 0.144"),
    ("( _mm9_ ) three managers", "(mm9) three managers"),
    ("(response = 97%; _n_ = 2022)", "(response = 97%; n = 2022)"),
    # <br> — разрыв строки внутри ячейки таблицы, а не текст
    ("1.Congratulate someone<br>2.Attend meetings",
     "1.Congratulate someone\n2.Attend meetings"),
    ("<u>подчёркнутое</u>", "подчёркнутое"),
    ("## 3 Results", "3 Results"),
    ("| Model | χ2 | df |", "  Model   χ2   df  "),
    ("|---|---|---|", ""),
    ("-----", ""),
    # подчёркивание внутри слова — не разметка, а часть текста
    ("файл snake_case и _курсив_", "файл snake_case и курсив"),
    ("two pape <mark>rs each we</mark> re", "two pape rs each we re"),
    ("research on ~~digital capability~~ (37", "research on digital capability (37"),
]

# Ссылки на литературу снимает эталон: они есть и в DOCX, и в OCR.
ЭТАЛОН = [
    ("analyses [35] and comprise", "analyses and comprise"),
    ("practice [31,34] and", "practice and"),
    ("shown [3–5].", "shown."),
    ("95% ci = [-.95; -.15]", "95% ci = [-.95; -.15]"),
    ("see [a] and [2019a]", "see [a] and [2019a]"),
]

плохо = 0
for дано, ждём in СЛУЧАИ:
    стало = b1.снять_разметку(дано)
    if стало != ждём:
        плохо += 1
        print(f"  X {дано!r}\n    ждали {ждём!r}\n    стало {стало!r}")
for дано, ждём in ЭТАЛОН:
    стало = b1.эталон(дано)
    if стало != ждём:
        плохо += 1
        print(f"  X эталон {дано!r}\n    ждали {ждём!r}\n    стало {стало!r}")

# Разделитель шапки считается по одному на таблицу — на нём стоит поле «таблиц».
таблица = "| a | b |\n|---|---|\n| 1 | 2 |"
сколько = len(b1.РАЗДЕЛИТЕЛЬ_ТАБЛИЦЫ.findall(таблица + "\n\n" + таблица))
if сколько != 2:
    плохо += 1
    print(f"  X две таблицы, насчитали {сколько}")

print(f"случаев: {len(СЛУЧАИ) + len(ЭТАЛОН) + 1}, расхождений: {плохо}")
sys.exit(1 if плохо else 0)
