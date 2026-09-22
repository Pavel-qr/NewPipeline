# -*- coding: utf-8 -*-
"""
Вызов Claude через Anthropic Messages API (router.cheap).

Ключ: `API_KEY` / `ANTHROPIC_API_KEY` в окружении или в `api.env` / `.env`
в корне `пайплайн_отбора/`.

  python3 _скрипты/модель.py          — проверка ключа коротким JSON-запросом
"""
import json, os, re, ssl, sys, time, urllib.error, urllib.request

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
КОРЕНЬ = os.path.dirname(ЗДЕСЬ)

БАЗА_ПО_УМОЛЧАНИЮ = "https://direct.router-cheap.com"
МОДЕЛЬ_ПО_УМОЛЧАНИЮ = "claude-opus-5"
ВЕРСИЯ_ПО_УМОЛЧАНИЮ = "2023-06-01"
ТАЙМАУТ = 900
ПОВТОРЫ = 3


def _подтянуть_env():
    """Читает ключ из `api.env` или `.env`. Уже заданные переменные не переписывает."""
    for имя in ("api.env", ".env"):
        путь = os.path.join(КОРЕНЬ, имя)
        if not os.path.isfile(путь):
            continue
        for сыр in open(путь, encoding="utf-8"):
            строка = сыр.strip()
            if not строка or строка.startswith("#") or "=" not in строка:
                continue
            ключ_, _, знач = строка.partition("=")
            ключ_, знач = ключ_.strip(), знач.strip().strip("'").strip('"')
            if ключ_ and ключ_ not in os.environ:
                os.environ[ключ_] = знач


def _из_env(*имена, умолчание=""):
    _подтянуть_env()
    for имя in имена:
        знач = (os.environ.get(имя) or "").strip()
        if знач:
            return знач
    return умолчание


def ключ():
    return _из_env("API_KEY", "ANTHROPIC_API_KEY")


def включен():
    """Есть ключ — оркестратор зовёт API; нет — прежняя остановка с кодом 2."""
    return bool(ключ())


def модель():
    return _из_env("API_MODEL", "ANTHROPIC_MODEL", умолчание=МОДЕЛЬ_ПО_УМОЛЧАНИЮ)


def _база():
    return _из_env("API_BASE", "ANTHROPIC_BASE_URL", "ANTHROPIC_BASE",
                   умолчание=БАЗА_ПО_УМОЛЧАНИЮ).rstrip("/")


def _url():
    база = _база()
    if база.endswith("/messages"):
        return база
    if база.endswith("/v1"):
        return база + "/messages"
    return база + "/v1/messages"


def _ssl_контекст():
    """У python.org на macOS часто нет корневых сертификатов — берём certifi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _макс_токенов():
    сыр = _из_env("API_MAX_TOKENS", "ANTHROPIC_MAX_TOKENS", умолчание="32768")
    try:
        return max(256, int(сыр))
    except ValueError:
        return 32768


_УРОВНИ_EFFORT = ("low", "medium", "high", "xhigh", "max")


def _температура():
    """None — не слать поле. Официальный Anthropic на Opus 5 отвергает
    ненулевую температуру; router.cheap принимает."""
    сыр = _из_env("API_TEMPERATURE", "ANTHROPIC_TEMPERATURE")
    if not сыр:
        return None
    return float(сыр)


def _effort():
    """None — дефолт API (`high`). Иначе low|medium|high|xhigh|max."""
    сыр = _из_env("API_EFFORT", "ANTHROPIC_EFFORT").strip().lower()
    if not сыр:
        return None
    if сыр not in _УРОВНИ_EFFORT:
        raise RuntimeError(
            f"API_EFFORT={сыр!r}: допустимо {', '.join(_УРОВНИ_EFFORT)}")
    return сыр


def разобрать_json(текст):
    """Снимает markdown-ограду и отдаёт объект. Пусто или не JSON — ValueError."""
    s = (текст or "").strip()
    if not s:
        raise ValueError("пустой ответ модели")
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```\s*$", "", s)
        s = s.strip()
    if not s:
        raise ValueError("пустой ответ модели")
    i = min((p for p in (s.find("{"), s.find("[")) if p >= 0), default=-1)
    if i < 0:
        raise ValueError("в ответе модели нет JSON")
    if i > 0:
        s = s[i:]
    объект, _ = json.JSONDecoder().raw_decode(s)
    return объект


def _текст_блоков(блоки):
    части = []
    for ч in блоки or []:
        if isinstance(ч, str):
            части.append(ч)
        elif isinstance(ч, dict):
            if ч.get("type") in (None, "text", "output_text") and ч.get("text"):
                части.append(ч["text"])
            elif ч.get("type") == "thinking":
                continue
    return "".join(части)


def _usage(данные):
    сыр = (данные or {}).get("usage") or {}
    return {
        "prompt_tokens": int(сыр.get("prompt_tokens") or сыр.get("input_tokens") or 0),
        "completion_tokens": int(сыр.get("completion_tokens") or сыр.get("output_tokens") or 0),
    }


def _тело_ответа(данные):
    """Anthropic /v1/messages → текст из content[]."""
    if not isinstance(данные, dict):
        raise ValueError(f"ответ API не объект: {type(данные).__name__}")
    ошибка = данные.get("error")
    if ошибка:
        if isinstance(ошибка, dict):
            raise ValueError(f"ошибка API: {ошибка.get('message') or ошибка}")
        raise ValueError(f"ошибка API: {ошибка}")
    if данные.get("type") == "error":
        raise ValueError(f"ошибка API: {данные}")
    блоки = данные.get("content")
    if not isinstance(блоки, list):
        raise ValueError("в ответе API нет content[] (ожидался Anthropic /v1/messages)")
    текст = _текст_блоков(блоки)
    if not текст:
        for ч in блоки:
            if isinstance(ч, dict) and ч.get("type") == "tool_use":
                inp = ч.get("input")
                if isinstance(inp, dict) and inp:
                    return json.dumps(inp, ensure_ascii=False), _usage(данные)
                if isinstance(inp, str) and inp.strip():
                    return inp, _usage(данные)
        типы = [ч.get("type") if isinstance(ч, dict) else type(ч).__name__ for ч in блоки]
        raise ValueError(
            f"в ответе API пустой content (stop={данные.get('stop_reason')}, blocks={типы})")
    return текст, _usage(данные)


def _заголовки(токен):
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": токен,
        "Authorization": "Bearer " + токен,
        "anthropic-version": _из_env("ANTHROPIC_VERSION", умолчание=ВЕРСИЯ_ПО_УМОЛЧАНИЮ),
    }


def _http_json(method, url, токен, тело=None, timeout=60):
    данные = None if тело is None else json.dumps(тело, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=данные, headers=_заголовки(токен), method=method)
    ctx = _ssl_контекст()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as отв:
            return json.loads(отв.read().decode("utf-8"))
    except urllib.error.HTTPError as сбой:
        кусок = сбой.read().decode("utf-8", errors="replace")[:800]
        if сбой.code in (401, 403):
            raise RuntimeError("API отклонил ключ (401/403). Проверьте API_KEY.") from сбой
        raise RuntimeError(f"HTTP {сбой.code}: {кусок}") from сбой
    except (urllib.error.URLError, TimeoutError, OSError) as сбой:
        raise RuntimeError(f"сеть: {сбой}") from сбой


def _антропик_сообщения(сообщения):
    """system — отдельное поле; в messages только user/assistant, первым — user."""
    система, диалог = [], []
    for с in сообщения:
        роль = с.get("role")
        текст = с.get("content") or ""
        if роль == "system":
            система.append(текст)
        elif роль in ("user", "assistant"):
            диалог.append({"role": роль, "content": текст})
        else:
            диалог.append({"role": "user", "content": текст})
    if диалог and диалог[0]["role"] != "user":
        диалог.insert(0, {"role": "user", "content": "(начало)"})
    return "\n\n".join(система).strip(), диалог


def спросить(сообщения, json_object=True, effort=None):
    """POST /v1/messages. json_object остаётся в промте: разбирает `разобрать_json`.
    effort шага; `API_EFFORT` в env перекрывает, если задан."""
    токен = ключ()
    if not токен:
        raise RuntimeError("нет API_KEY — задайте ключ в api.env или .env")
    система, диалог = _антропик_сообщения(сообщения)
    полезная = {
        "model": модель(),
        "max_tokens": _макс_токенов(),
        "stream": False,
        "messages": диалог,
        "tool_choice": {"type": "none"},
    }
    температура = _температура()
    if температура is not None:
        полезная["temperature"] = температура
    уровень = _effort() or effort
    if уровень:
        полезная["output_config"] = {"effort": уровень}
    if система:
        полезная["system"] = система
    url = _url()
    последняя = None
    for попытка in range(1, ПОВТОРЫ + 1):
        try:
            данные = _http_json("POST", url, токен, полезная, timeout=ТАЙМАУТ)
            текст, usage = _тело_ответа(данные)
            return разобрать_json(текст) if json_object else текст, usage
        except (RuntimeError, ValueError) as сбой:
            последняя = сбой
            текст_сбоя = str(сбой)
            стоит_повторить = (
                "HTTP 429" in текст_сбоя or "HTTP 529" in текст_сбоя
                or "HTTP 5" in текст_сбоя or "пустой content" in текст_сбоя
                or "пустой ответ" in текст_сбоя or текст_сбоя.startswith("сеть:")
                or "Expecting value" in текст_сбоя or "нет JSON" in текст_сбоя
                or "Expecting ',' delimiter" in текст_сбоя
                or "Expecting property name" in текст_сбоя
                or "tool_use" in текст_сбоя
            )
            if not стоит_повторить:
                raise
            if попытка == ПОВТОРЫ:
                break
            print(f"    повтор {попытка}/{ПОВТОРЫ}: {текст_сбоя[:180]}")
            time.sleep(min(30, 5 * попытка))
    raise последняя


def _канон_текст(вид):
    import importlib.util as iu
    сп = iu.spec_from_file_location("канон", os.path.join(ЗДЕСЬ, "канон.py"))
    м = iu.module_from_spec(сп)
    сп.loader.exec_module(м)
    return м.в_текст(м.вид(вид))


def пользовательский_текст(ш, папка, строка_jsonl=None):
    """Тот же состав, что `_вызов.md`, но для одного вызова: либо все файлы,
    либо одна строка первого jsonl + остальные входы целиком."""
    import importlib.util as iu
    сп = iu.spec_from_file_location("шаги", os.path.join(ЗДЕСЬ, "шаги.py"))
    шаги = iu.module_from_spec(сп)
    сп.loader.exec_module(шаги)

    части = []
    входы = list(ш["входы"])
    if строка_jsonl is not None:
        части += [f"## Файл входа: {входы[0]} (одна строка этого вызова)",
                  "```json", строка_jsonl.strip(), "```"]
        входы = входы[1:]
    for в in входы:
        if в.startswith(шаги.КАНОН):
            имя = в[len(шаги.КАНОН):]
            if имя != "topics_индикаторы.xlsx":
                raise RuntimeError(f"как давать модели {в}, не объявлено")
            части += [f"## Файл входа: канон тем (вид «{ш['канон_вид']}», {имя})",
                      _канон_текст(ш["канон_вид"])]
            continue
        п = шаги.путь_входа(в, папка)
        if not (п and os.path.exists(п)):
            части += [f"## Файл входа: {в}",
                      "(файла нет — вход условный, шаг обошёлся без него)"]
            continue
        содержимое = open(п, encoding="utf-8").read()
        части += [f"## Файл входа: {в}",
                  "```json" if в.endswith((".json", ".jsonl")) else "```",
                  содержимое.rstrip(), "```"]
    выход = os.path.join(папка, ш["выходы"][0])
    части += ["## Куда положить ответ",
              f"Верни один JSON-объект по схеме раздела «Выход» промта. "
              f"Без markdown-ограды. Файл на диске запишет скрипт: `{выход}`."]
    return "\n".join(части)


def сообщения(ш, папка, строка_jsonl=None):
    промт = open(os.path.join(КОРЕНЬ, "_промты", ш["чем"]), encoding="utf-8").read()
    return [
        {"role": "system", "content": промт.strip()},
        {"role": "user", "content": пользовательский_текст(ш, папка, строка_jsonl)},
    ]


def _элементы_тем(объект):
    if isinstance(объект, dict) and isinstance(объект.get("темы"), list):
        return объект["темы"]
    if isinstance(объект, dict):
        return [объект]
    raise ValueError("ожидался объект или {\"темы\": [...]}")


def выполнить_шаг(ш, папка):
    """Все вызовы шага. Пишет выход. Печатает расход токенов, если API его отдал."""
    выход = os.path.join(папка, ш["выходы"][0])
    промт_имя = ш["чем"]
    usage_всего = {"prompt_tokens": 0, "completion_tokens": 0}

    def учесть(usage):
        usage_всего["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        usage_всего["completion_tokens"] += int(usage.get("completion_tokens") or 0)

    if ш.get("по_строке"):
        путь_строк = os.path.join(папка, ш["входы"][0])
        строки = [л for л in open(путь_строк, encoding="utf-8") if л.strip()]
        ответы = []
        уровень = ш.get("effort")
        for i, строка in enumerate(строки, 1):
            print(f"    API {промт_имя}: строка {i}/{len(строки)}"
                  + (f" effort={уровень}" if уровень else ""))
            объект, usage = спросить(сообщения(ш, папка, строка), effort=уровень)
            учесть(usage)
            ответы.append(объект)
        if выход.endswith(".jsonl"):
            with open(выход, "w", encoding="utf-8") as f:
                for объект in ответы:
                    f.write(json.dumps(объект, ensure_ascii=False) + "\n")
        else:
            темы = []
            for объект in ответы:
                темы.extend(_элементы_тем(объект))
            with open(выход, "w", encoding="utf-8") as f:
                json.dump({"темы": темы}, f, ensure_ascii=False, indent=2)
                f.write("\n")
    else:
        уровень = ш.get("effort")
        print(f"    API {промт_имя}: один вызов"
              + (f" effort={уровень}" if уровень else ""))
        объект, usage = спросить(сообщения(ш, папка), effort=уровень)
        учесть(usage)
        with open(выход, "w", encoding="utf-8") as f:
            json.dump(объект, f, ensure_ascii=False, indent=2)
            f.write("\n")

    pt, ct = usage_всего["prompt_tokens"], usage_всего["completion_tokens"]
    if pt or ct:
        print(f"    токены: вход {pt}, выход {ct}")
    return выход


def main():
    if not включен():
        print("API_KEY не задан. Впишите ключ в файл api.env "
              f"в папке:\n  {КОРЕНЬ}")
        return 1
    print("модель:", модель())
    print("url:", _url())
    print("temperature:", _температура())
    print("effort:", _effort() or "high (дефолт API)")
    объект, usage = спросить([
        {"role": "system", "content": "Ответь только JSON-объектом, без текста вокруг."},
        {"role": "user", "content": 'Верни {"ok": true, "model": "%s"}.' % модель()},
    ])
    print("ответ:", json.dumps(объект, ensure_ascii=False))
    if usage:
        print("токены:", usage)
    return 0 if объект.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
