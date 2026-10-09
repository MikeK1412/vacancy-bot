"""Разбор текста вакансии без нейросети: заголовок, работодатель, суть, оплата, удаление контактов."""
import re

# --- нормализация и ключевые слова ----------------------------------------

def norm(text):
    return text.lower().replace("ё", "е")


def load_keywords(path):
    """Читает keywords.txt: {раздел: [фразы]}."""
    sections, current = {}, None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections[current] = []
        elif current:
            sections[current].append(norm(line))
    return sections


def find_any(text, phrases):
    """Первая найденная фраза из списка или None. text уже нормализован.

    Фразы из 1–3 знаков ищутся только отдельным словом (иначе «b2» находится в «b2b»).
    """
    for p in phrases:
        if len(p) <= 3:
            if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", text):
                return p
        elif p in text:
            return p
    return None


def latin_share(text):
    """Доля латинских букв среди всех букв (для вакансий, написанных целиком на английском)."""
    letters = re.findall(r"[a-zа-я]", norm(text))
    if not letters:
        return 0.0
    return sum(c <= "z" for c in letters) / len(letters)


# --- контакты ------------------------------------------------------------

_URL = re.compile(r"(?:https?://|www\.|t\.me/|forms\.gle/)\S+", re.I)
_EMAIL = re.compile(r"\S+@\S+\.\w+")
_MENTION = re.compile(r"@\w{3,}")
_PHONE = re.compile(r"\+?\d[\d\s\-()]{8,}\d")
_CONTACT_LINE = re.compile(r"^\s*(?:📝|📩|✉️|☕️|откликнуться|отклик|контакт|писать|пишите|резюме присылайте|связь)", re.I)


def strip_contacts(text):
    text = _URL.sub("", text)
    text = _EMAIL.sub("", text)
    text = _MENTION.sub("", text)
    text = _PHONE.sub("", text)
    text = re.sub(r"\(\s*\)", "", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip(" ,;:–—-")


# --- заголовок, работодатель, суть ---------------------------------------

# Служебная строка в квадратных скобках: «[Свежая вакансия]», «[Удалёнка]», «[Свежий сценарий]» (Freelance Choice)
_META_LINE = re.compile(r"^\s*\[[^\]\n]{1,30}\]\s*$")
_LEADING_JUNK = re.compile(r"^[^\wА-Яа-яЁё(]+")
_SEEK = re.compile(r"[^.!?\n]*\b(?:ищ(?:ем|ут|у)|требуется|требуются|в поисках|нужен|нужна)\b[^.!?\n]*", re.I)
_FIELD = re.compile(r"^\s*(работодатель|где|компания|заказчик)\s*:\s*(.+)$", re.I)
_TASKS_HEADER = re.compile(
    r"^\W*(задачи|обязанности|что (?:нужно|предстоит|будет нужно) делать|что делать|чем (?:предстоит|нужно|вы будете) заниматься"
    r"|вам предстоит|что предстоит|функционал|что нужно)\b", re.I)
_SKIP_LINE = re.compile(r"^\s*(з/п|зп|зарплата|оплата|доход|формат|график|опыт|работодатель|где|компания|о вакансии)\s*:", re.I)
_BULLET = re.compile(r"^\s*(?:[-–—•·*▪️✏️🔹🔸✅➖]|\d+[.)])\s*")


def _clean_title(line):
    line = line.replace("#", "").replace("_", " ")
    line = _LEADING_JUNK.sub("", line).strip()
    line = re.sub(r"^\d{1,2}\.\s*", "", line)  # номер пункта дайджеста
    line = strip_contacts(line)
    return line.rstrip(" .:")


# Куски заголовка про формат и деньги: в сообщении они лишние (оплата идёт отдельной строкой)
_TITLE_NOISE = re.compile(
    r"удал[её]н|remote|услови|в лс|занятост|оплат|з/п|\bзп\b|₽|руб|тыс|\d+\s*к\b|\$|€|офис|гибрид|полный день"
    r"|график|фултайм|full.?time|part.?time|проектн", re.I)
_TITLE_FIXES = {
    "контентменеджер": "контент-менеджер",
    "контентмаркетолог": "контент-маркетолог",
    "контентмейкер": "контент-мейкер",
    "смм": "SMM",
}
TITLE_LIMIT = 80


def tidy_title(title):
    """Чистит заголовок: формат и оплата из шапки, повторы слов, эмодзи, опечатки вида «Контентменеджер», длина."""
    t = re.sub(r"\(\s*удал[её]нк\w*\s*\)", "", title, flags=re.I)
    # «ИП Иванова Анна Сергеевна», «ИП Петров А. В.» — убираем вместе с ФИО
    t = re.sub(r"(?:\s+(?:в|у|от)\s+|\s*[—–-]\s*)?\bИП\s+[«\"]?[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ](?:[а-яё]+|\.)){0,2}[»\"]?", "", t)
    t = re.sub(r"^\s*(?:требуется|требуются)\s+", "", t, flags=re.I)
    t = re.sub(r"^\s*(?:ну,?\s*)?(?:а\s+)?(?:ещ[её]\s+)?(?:сегодня|сейчас|кроме того,?)\s+", "", t, flags=re.I)
    # «Копирайтер, сценарии | онлайн-школа | удалёнка | 30 тыс.» → убираем куски про формат и деньги
    parts = [p.strip() for p in re.split(r"\s*\|\s*", t)]
    parts = [parts[0]] + [p for p in parts[1:] if p and not _TITLE_NOISE.search(p)]
    pieces = []
    for part in parts:
        commas = [c.strip() for c in part.split(",")]
        commas = [commas[0]] + [c for c in commas[1:] if c and not _TITLE_NOISE.search(c)]
        pieces.append(", ".join(commas))
    t = " — ".join(p for p in pieces if p)
    t = re.sub(r"[^\w\s.,:;!?«»\"'()/&+№%—–-]", "", t)            # эмодзи и значки
    t = re.sub(r"\b(\w+)(?:\s+\1\b)+", r"\1", t, flags=re.I)      # «TransPerfect TransPerfect»
    t = re.sub(r"(\w)-\s+(\w)", lambda m: m.group(1) + "-" + m.group(2).lower(), t)  # «Копирайтер- Сценарист»
    for wrong, right in _TITLE_FIXES.items():
        t = re.sub(rf"\b{wrong}\b", lambda m, r=right: r.capitalize() if m.group(0)[0].isupper() and r.islower() else r,
                   t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,;:—–-|.")
    if len(t) > TITLE_LIMIT:
        t = t[:TITLE_LIMIT].rsplit(" ", 1)[0].rstrip(",;:—–-") + "…"
    return t[:1].upper() + t[1:]


def title_of(item):
    """Заголовок: первая содержательная строка, для «болтливых» постов первая фраза с «ищем/требуется»."""
    lines = [l for l in item.text.split("\n") if l.strip() and not _META_LINE.match(l)]
    if not lines:
        return ""
    first = _clean_title(lines[0].strip("[] "))
    seek = None
    if len(first) > 120 or not re.search(r"[А-Яа-яA-Za-z]{4,}", first) or re.match(r"(доброе|добрый|привет|друзья|коллеги)", norm(first)):
        m = _SEEK.search(item.text)
        if m:
            seek = _clean_title(m.group(0).strip("[] "))
    title = seek or first
    return title[:120].rsplit(" ", 1)[0] + "…" if len(title) > 120 else title


def employer_of(item):
    for line in item.text.split("\n"):
        m = _FIELD.match(line)
        if m:
            # частное лицо («ИП Иванова А. С.», «Ильиных Э. С.») в сообщение не выводим
            if re.fullmatch(r"(?:ИП\s+)?[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ](?:[а-яё]+|\.))+\.?", m.group(2).strip()):
                return ""
            value = strip_contacts(re.split(r"(?<=[.!?])\s", m.group(2).strip())[0]).rstrip(".")
            return value[:70].rsplit(" ", 1)[0] + "…" if len(value) > 70 else value
    return ""


_REQ_HEADER = re.compile(
    r"^\W*(требования|кого (?:мы )?ищ|что (?:мы )?ждем|что (?:мы )?ждём|ждем от|ждём от|ожидания|нам важно|вы нам подходите"
    r"|что нужно от вас|что важно)\b", re.I)
SUMMARY_LIMIT = 280


def _section_points(lines, start, header_re, limit):
    """Пункты списка после строки-заголовка (до пустой строки или следующего заголовка)."""
    line = lines[start]
    after = line.split(":", 1)[1].strip() if ":" in line else ""
    points = [after] if after else []
    for nxt in lines[start + 1:]:
        if not nxt:
            if points:
                break
            continue
        if header_re.match(nxt) or _TASKS_HEADER.match(nxt) or _REQ_HEADER.match(nxt) or (nxt.endswith(":") and len(nxt) < 40):
            break
        if _CONTACT_LINE.match(nxt):
            break
        points.append(_BULLET.sub("", nxt).strip().rstrip(";,."))
        if len(points) >= limit:
            break
    return [strip_contacts(p) for p in points if p]


def summary_of(item, limit=SUMMARY_LIMIT):
    """Суть в 2–3 строки: задачи и главное требование, иначе первые фразы описания. Перечисления через запятую."""
    lines = [l.strip() for l in item.text.split("\n")]
    tasks, req = [], []
    for i, line in enumerate(lines):
        if not tasks and _TASKS_HEADER.match(line):
            tasks = _section_points(lines, i, _TASKS_HEADER, 3)
        elif not req and _REQ_HEADER.match(line):
            req = _section_points(lines, i, _REQ_HEADER, 1)
    if tasks:
        text = _sentence(", ".join(_lower_first(p) for p in tasks))
        if req:
            text += " " + _sentence(req[0])
        return _shorten(text, limit)
    body, cut_early = [], False
    for line in lines[1:]:
        if not line or _SKIP_LINE.match(line) or _CONTACT_LINE.match(line) or _META_LINE.match(line):
            continue
        if line.startswith("#") and " " not in line.strip("#"):
            continue
        line = re.sub(r"^\W*(требования|задачи|обязанности|условия)\s*:\s*", "", line, flags=re.I)
        body.append(_BULLET.sub("", line))
        if sum(len(b) for b in body) > limit:
            cut_early = True  # дальше в посте ещё есть текст
            break
    text = strip_contacts(" ".join(body).replace("#", "")).replace("[", "").replace("]", "")
    # приветствия авторов («Доброе утро, дорогие.») в суть не берём
    text = re.sub(r"(?:^|(?<=[.!?]\s))(?:доброе|добрый|привет|всем привет|друзья|коллеги)[^.!?]*[.!?]\s*", "", text, flags=re.I)
    text = _shorten(text, limit)
    if cut_early and not text.endswith("…"):
        text = text.rstrip(" .,;:—–-") + "…"  # описание обрезано: многоточие, даже если вырезанная ссылка его укоротила
    return text


def _lower_first(s):
    return s[:1].lower() + s[1:] if s[1:2].islower() else s


def _sentence(s):
    s = s.strip().rstrip(";,:")
    s = s[:1].upper() + s[1:]
    return s if s.endswith((".", "!", "?", "…")) else s + "."


def _uncaps(text):
    """«ИЩЕМ SMM-ВОЛШЕБНИКА В КОМАНДУ» → «Ищем smm-волшебника в команду» (только для фраз капсом)."""
    def fix(m):
        s = m.group(0)
        letters = [c for c in s if c.isalpha()]
        if len(letters) > 12 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
            first = next(i for i, c in enumerate(s) if c.isalpha())
            return s[: first + 1] + s[first + 1:].lower()
        return s
    text = re.sub(r"[^.!?]+[.!?]?", fix, text)
    # отдельные слова капсом («СРАЗУ») тоже; аббревиатуры из 2–3 букв (SEO, СМИ, ВК) не трогаем
    return re.sub(r"\b[А-ЯЁ]{4,}\b", lambda m: m.group(0) if m.group(0) in _KEEP_CAPS else m.group(0).lower(), text)


_KEEP_CAPS = {"МАКС", "НИУ", "ВШЭ", "МГУ", "СПБГУ", "РАНХИГС"}


def _shorten(text, limit):
    """Сокращает до limit знаков: по концу предложения, а если не выходит, по слову с «…». «;» → «,»."""
    text = re.sub(r"\s*;\s*", ", ", text)
    text = _uncaps(re.sub(r"\s+", " ", text).strip())
    text = re.sub(r",\s*,", ",", text).strip(" ,")
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("…"))
    if end > limit * 0.4:
        cut = cut[: end + 1]
    else:
        cut = cut.rsplit(" ", 1)[0]
    # текст обрезан: всегда заканчиваем многоточием
    return cut.rstrip(" .,;:—–-") + "…"


# --- оплата ---------------------------------------------------------------

_MONEY = re.compile(
    r"(?:(?:от|до)\s*)?\d[\d\s .,]*(?:\s*[-–—]\s*(?:до\s*)?\d[\d\s .,]*)?\s*"
    r"(?:₽|руб|р\.|рубл|тыс|т\.\s?р|k\b|к\b|\$|€|usd|usdt|долл|евро)", re.I)
_HASHTAG_PAY = re.compile(r"#(?:от(\d+))?(?:до(\d+))?к\b", re.I)
_PAY_LABEL = re.compile(r"^\W*(з/п|зп|зарплата|оплата|доход|ставка|гонорар|вознаграждение)\s*[:—–-]?\s*", re.I)
_PAY_DROP = re.compile(r"удал[её]н|remote|офис|гибрид|занятост|график|формат|полный день", re.I)


NBSP = " "
_PERIODS = [
    (r"в\s+месяц|/\s*мес|за\s+месяц|ежемесячно|в\s+мес\b|оклад", "/мес"),
    (r"в\s+час|/\s*час|за\s+час", "/час"),
    (r"в\s+день|за\s+день", "/день"),
    (r"за\s+смену", "за смену"),
    (r"за\s+1\s*000\s+знаков|за\s+1000\s+знаков|за\s+тысячу\s+знаков", "за 1000 знаков"),
    (r"за\s+(статью|задачу|проект|ролик|видео|сценарий|материал|пост|текст|выпуск|серию|рецензию)", None),
]


def _thousands(n):
    return f"{n:,}".replace(",", NBSP)


def _amounts(chunk):
    """Числа из суммы с учётом «тыс», «к», «т.р.»: «50-60 тыс.» → [50000, 60000]."""
    mult = 1000 if re.search(r"тыс|т\.\s?р|\d\s*[кk]\b", chunk, re.I) else 1
    nums = []
    for raw in re.findall(r"\d[\d\s ]*(?:[.,]\d+)?", chunk):
        raw = re.sub(r"[\s ]", "", raw).replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            continue
        if mult > 1 and value < 1000:
            value *= mult
        nums.append(int(round(value)))
    return nums


def format_pay(chunk, tail=""):
    """Единый вид оплаты: «от 50 000 ₽/мес», «50 000–60 000 ₽/мес», «до 100 000 ₽/мес», «2 000 ₽ за задачу».

    chunk — найденная сумма, tail — несколько слов после неё (там бывает «в месяц», «за статью»).
    Если разобрать не получилось, возвращает пустую строку.
    """
    nums = _amounts(chunk)
    if not nums:
        return ""
    low = norm(chunk + " " + tail)
    if re.search(r"\$|usd(?!t)|долл", low):
        cur = "$"
    elif re.search(r"€|евро|eur", low):
        cur = "€"
    elif "usdt" in low:
        cur = "USDT"
    else:
        cur = "₽"
    period = ""
    for pattern, label in _PERIODS:
        m = re.search(pattern, low)
        if m:
            period = label if label else " " + m.group(0)
            break
    if period and not period.startswith("/"):
        period = " " + period.strip()
    if len(nums) >= 2 and nums[1] > nums[0]:
        amount = f"{_thousands(nums[0])}–{_thousands(nums[1])}"
    elif re.match(r"\s*до\b", low):
        amount = f"до {_thousands(nums[0])}"
    elif re.match(r"\s*от\b", low) or re.search(r"\bот\s*$", tail):
        amount = f"от {_thousands(nums[0])}"
    else:
        amount = _thousands(nums[0])
    return f"{amount}{NBSP}{cur}{period}"


def pay_of(item):
    """Оплата в едином виде («от 50 000 ₽/мес»), если в тексте есть сумма с валютой, иначе пустая строка."""
    for line in item.text.split("\n"):
        m = _MONEY.search(line)
        if m and re.search(r"\d", m.group(0)):
            # «от 100 000 до 120 000 ₽»: сумма-регулярка ловит только «до 120 000 ₽», добираем начало диапазона
            before = line[max(0, m.start() - 30): m.start()]
            start = re.search(r"(от\s*\d[\d\s .,]*(?:тыс\.?|к)?\s*)$", before, re.I)
            if start and not m.group(0).lower().startswith("от"):
                chunk = start.group(1) + m.group(0)
            else:
                chunk = ("от " if re.search(r"\bот\s*$", before, re.I) else "") + m.group(0)
            tail = re.split(r"[.;!?\n]", line[m.end(): m.end() + 40].lstrip(". "))[0]  # «тыс. в месяц»
            formatted = format_pay(chunk, tail)
            if formatted:
                return formatted
            value = strip_contacts(_BULLET.sub("", _PAY_LABEL.sub("", line.strip()))).replace("#", "")
            return _shorten(value, 90).rstrip(".")
    m = _HASHTAG_PAY.search(item.text)
    if m and (m.group(1) or m.group(2)):
        lo, hi = m.group(1), m.group(2)
        if lo and hi:
            return f"{_thousands(int(lo) * 1000)}–{_thousands(int(hi) * 1000)}{NBSP}₽/мес"
        return f"от {_thousands(int(lo) * 1000)}{NBSP}₽/мес" if lo else f"до {_thousands(int(hi) * 1000)}{NBSP}₽/мес"
    return ""


# --- контакты для отклика ---------------------------------------------------

_LINK = re.compile(r"(?:https?://|(?<![\w/.])t\.me/|(?<![\w/.])forms\.gle/)[^\s<>«»\"')]+", re.I)
_EMAIL_FULL = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.I)
_NICK = re.compile(r"(?<![\w.@])@([A-Za-z][\w]{3,})")


def _link_key(url):
    u = url.lower().rstrip(".,;:!?)")
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    if "hh.ru/vacancy/" in u:
        u = u.split("?", 1)[0]
    return u


def contacts_of(item):
    """Способы отклика из текста: [(ключ, вид, как показать)], вид: nick | email | phone | link | instagram.

    Ключ одинаковый для одного контакта в разных постах (по нему склеиваются дубли).
    """
    text, own = item.text, item.channel.lower()
    found, seen = [], set()

    def add(key, kind, shown):
        if key not in seen:
            seen.add(key)
            found.append((key, kind, shown))

    for m in _NICK.finditer(text):
        nick = m.group(1)
        if nick.lower() != own:
            add("@" + nick.lower(), "nick", "@" + nick)
    for m in _EMAIL_FULL.finditer(text):
        add(m.group(0).lower(), "email", m.group(0))
    for m in re.finditer(r"(?<!\d)(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)", text):
        digits = re.sub(r"\D", "", m.group(0))[-10:]
        add(digits, "phone", f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:]}")  # «+7 965 574-98-97»
    for m in _LINK.finditer(text):
        url = m.group(0).rstrip(".,;:!?)")
        key = _link_key(url)
        if key.startswith((f"t.me/{own}/", f"t.me/s/{own}")) or key == f"t.me/{own}":
            continue
        if not url.lower().startswith("http"):
            url = "https://" + url
        kind = "instagram" if "instagram.com" in key else "link"
        add(key, kind, url)
    return found


def contact_button(item):
    """Есть ли под постом кнопка для получения контакта или отклика (Текстодром, SEO HR)."""
    return any(re.search(r"контакт|отклик", norm(text)) for text, _ in item.extra.get("buttons", []))


def digest_number(item):
    """Номер пункта в подборке, как он написан в посте («16. #Копирайтер» → 16)."""
    m = re.match(r"\s*(\d{1,2})\.", item.text)
    return int(m.group(1)) if m else item.part


# --- опыт и формат ------------------------------------------------------------

_NUM_WORDS = {"одного": 1, "года": 1, "двух": 2, "трех": 3, "трёх": 3, "четырех": 4, "пяти": 5, "шести": 6}
_YEARS = re.compile(
    r"(\d+(?:[.,]\d+)?|одного|двух|трех|четырех|пяти|шести)\s*(?:-?х)?\s*\+?\s*(?:[-–]\s*\d+\s*(?:-?х)?\s*)?(?:лет|года|год)\b"
    r"|от\s+(года)\b")


MIN_SENIOR_YEARS = 3


def experience_years(item):
    """Сколько лет опыта требуют (наибольшее из найденных требований) или None, если не сказано."""
    t = norm(item.text)
    found = []
    for m in re.finditer(r"опыт", t):
        window = re.split(r"[.;\n]", t[m.start(): m.start() + 90])[0]
        y = _YEARS.search(window)
        if y:
            found.append(y)
    for m in re.finditer(r"от\s+[^.;\n]{0,15}?(?:лет|года)\s+(?:опыта|работы|в профессии)", t):
        y = _YEARS.search(m.group(0))
        if y:
            found.append(y)
    years = []
    for y in found:
        raw = y.group(1) or y.group(2)
        years.append(_NUM_WORDS.get(raw) or float(raw.replace(",", ".")))
    if re.search(r"\bsenior\b|сеньор|синьор", t):
        years.append(MIN_SENIOR_YEARS)  # «уровня senior» без цифры = опыт от трёх лет
    return max(years) if years else None


def no_experience(item):
    t = norm(item.text)
    if re.search(r"без опыта|опыт не (?:нужен|требуется|обязател)|для начинающих", t):
        return True
    # «новичков не рассматриваем», «не для новичков» — это наоборот
    for m in re.finditer(r"новичк\w*", t):
        around = t[max(0, m.start() - 15): m.end() + 20]
        if not re.search(r"\bне\b|нельзя|без новичк", around):
            return True
    return False


def work_format(item, remote_words):
    """Метки формата работы, которые нашлись в посте: удалёнка, частичная, проект."""
    t = norm(item.context + "\n" + item.text)
    labels = []
    if any(w in t for w in remote_words):
        labels.append("удалёнка")
    if re.search(r"частичн|неполн|part.?time|подработ", t):
        labels.append("частичная")
    if re.search(r"проектн|разов|сдельн|за проект|за ролик|за статью|за сценарий|за видео|за материал", t):
        labels.append("проект")
    return labels
