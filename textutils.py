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
    t = re.sub(r"^\s*(?:требуется|требуются)\s+", "", t, flags=re.I)
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
            value = strip_contacts(re.split(r"(?<=[.!?])\s", m.group(2).strip())[0]).rstrip(".")
            return value[:70].rsplit(" ", 1)[0] + "…" if len(value) > 70 else value
    return ""


def summary_of(item, limit=220):
    """Суть в 1–2 строки: первые пункты задач, иначе первые фразы описания."""
    lines = [l.strip() for l in item.text.split("\n")]
    for i, line in enumerate(lines):
        if _TASKS_HEADER.match(line):
            after = line.split(":", 1)[1].strip() if ":" in line else ""
            points = [after] if after else []
            for nxt in lines[i + 1:]:
                if not nxt:
                    if points:
                        break
                    continue
                if _TASKS_HEADER.match(nxt) or (nxt.endswith(":") and len(nxt) < 40):
                    break
                points.append(_BULLET.sub("", nxt).rstrip(";,."))
                if len(points) >= 3:
                    break
            text = strip_contacts("; ".join(p for p in points if p))
            if text:
                return _shorten(text, limit)
    body = []
    for line in lines[1:]:
        if not line or _SKIP_LINE.match(line) or _CONTACT_LINE.match(line) or _META_LINE.match(line):
            continue
        if line.startswith("#") and " " not in line.strip("#"):
            continue
        body.append(_BULLET.sub("", line))
        if sum(len(b) for b in body) > limit:
            break
    text = strip_contacts(" ".join(body).replace("#", ""))
    return _shorten(text, limit)


def _uncaps(text):
    """«ИЩЕМ SMM-ВОЛШЕБНИКА В КОМАНДУ» → «Ищем smm-волшебника в команду» (только для фраз капсом)."""
    def fix(m):
        s = m.group(0)
        letters = [c for c in s if c.isalpha()]
        if len(letters) > 12 and sum(c.isupper() for c in letters) / len(letters) > 0.7:
            first = next(i for i, c in enumerate(s) if c.isalpha())
            return s[: first + 1] + s[first + 1:].lower()
        return s
    return re.sub(r"[^.!?]+[.!?]?", fix, text)


def _shorten(text, limit):
    text = _uncaps(re.sub(r"\s+", " ", text).strip())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "))
    if end > limit * 0.5:
        return cut[: end + 1].rstrip(";")
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"


# --- оплата ---------------------------------------------------------------

_MONEY = re.compile(
    r"(?:(?:от|до)\s*)?\d[\d\s .,]*(?:\s*[-–—]\s*(?:до\s*)?\d[\d\s .,]*)?\s*"
    r"(?:₽|руб|р\.|рубл|тыс|т\.\s?р|k\b|к\b|\$|€|usd|usdt|долл|евро)", re.I)
_HASHTAG_PAY = re.compile(r"#(?:от(\d+))?(?:до(\d+))?к\b", re.I)
_PAY_LABEL = re.compile(r"^\W*(з/п|зп|зарплата|оплата|доход|ставка|гонорар|вознаграждение)\s*[:—–-]?\s*", re.I)


def pay_of(item):
    """Строка с оплатой, если в тексте есть сумма с валютой, иначе пустая строка."""
    for line in item.text.split("\n"):
        m = _MONEY.search(line)
        if m and re.search(r"\d", m.group(0)):
            value = _PAY_LABEL.sub("", line.strip())
            value = strip_contacts(_BULLET.sub("", value)).replace("#", "")
            if len(value) > 90:
                # длинная строка описания: берём сумму и несколько слов после неё («в месяц», «за видео»)
                after = re.split(r"[.;!?\n]", line[m.end(): m.end() + 30])[0]
                value = (m.group(0) + after).strip(" ,")
            return _shorten(value, 90)
    m = _HASHTAG_PAY.search(item.text)
    if m and (m.group(1) or m.group(2)):
        lo, hi = m.group(1), m.group(2)
        if lo and hi:
            return f"{lo}–{hi} тыс. ₽"
        return f"от {lo} тыс. ₽" if lo else f"до {hi} тыс. ₽"
    return ""
