# Самопроверка цитат для куска выжимок. Использует ту же логику, что Б4.
# python3 _скрипты/самопроверка.py материалы/<папка> <файл.jsonl>
import sys, os, json
ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ЗДЕСЬ)      # b4 лежит рядом; путей от cwd здесь нет
import b4_проверка_выжимок as b4
if len(sys.argv) < 3:
    raise SystemExit("python3 _скрипты/самопроверка.py материалы/<папка> <файл.jsonl>")
папка, файл = sys.argv[1], sys.argv[2]
текст = b4.норм(open(os.path.join(папка, "00_текст.txt"), encoding="utf-8").read())
плохо = 0; всего = 0
for строка in open(файл, encoding="utf-8"):
    строка = строка.strip()
    if not строка: continue
    в = json.loads(строка)
    for вид, ц in b4.собрать_цитаты(в):
        if not ц: continue
        всего += 1
        if not b4.найдена(ц, текст):
            плохо += 1; print(f'  X {в["чанк_id"]} [{вид}] {ц[:140]}')
print(f"цитат: {всего}, недословных: {плохо}")
sys.exit(1 if плохо else 0)
