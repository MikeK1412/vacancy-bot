"""Сообщение для группы (Telegram HTML).

Вакансия:
    1. Заголовок — работодатель        (жирный, ссылка на пост)
    Суть: задачи и главное требование, до 280 знаков
    💰 оплата · удалёнка · частичная · без опыта   (только то, что нашлось)
    ✉️ контакт
"""
import re
from html import escape

from textutils import (_META_LINE, _SEEK, _clean_title, TITLE_LIMIT, city_only, contacts_of, employer_of,
                       experience_years, no_experience, norm, pay_of, strip_contacts, strip_greeting, summary_of, tidy_title, title_of, work_format)

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]
FOOTER = "⚠️ Нормальный работодатель не берёт денег за обучение, тестовое или «доступ»."


def _abbr(text):
    """Аббревиатуры заглавными: «seo-статьи» → «SEO-статьи»."""
    return re.sub(r"\bseo\b", "SEO", text, flags=re.I)


_GENERIC_PLACES = {"команду", "команде", "проект", "штат", "компанию", "агентство", "нашу команду", "долгосрочное"}


def _qualifier(item, title):
    """Уточнение для общего заголовка («Копирайтер») из текста: кто ищет или для чего."""
    # только первая строка описания: дальше уже «Задачи», «Требования» и т.п.
    body = next((l.strip() for l in item.text.split("\n")[1:] if l.strip()), "")
    first = re.split(r"(?<=[.!?:])\s", body, 1)[0]
    # «Онлайн-школа по маркетингу ищет копирайтера» → «— онлайн-школа по маркетингу»
    m = re.match(r"([А-ЯЁA-Z«][^.!?:]{2,45}?)\s+(?:ищет|ищут|в поисках)\b", first)
    if m and not re.match(r"(?:мы|я|ищем|ищу|компания|команда|в|во)\b", m.group(1), re.I):
        who = m.group(1)
        return " — " + (who[:1].lower() + who[1:] if who[1:2].islower() else who)  # «ООО» не трогаем
    # «…копирайтера в команду для проектов экспертов и продюсеров» → «для проектов экспертов и продюсеров»
    for prep in ("для", "в", "во", "по"):
        for m in re.finditer(rf"\b{prep}\s+([^.,:;!?()]{{3,80}})", first):
            phrase = m.group(1).strip()
            if prep != "для":
                phrase = re.split(r"\s+(?:для|и нужно|нужно|которы\w*|чтобы)\b", phrase)[0]
            low = phrase.lower()
            cut_before_comma = first[m.end():m.end() + 1] == "," and re.search(r"(ых|их|ой|ый|ий|ая|ое|ые|ие)$", low)
            if cut_before_comma:
                continue
            if low in _GENERIC_PLACES or low.split()[0] in _TIME_WORDS or low[:1].isdigit():
                continue
            if len(phrase) > _QUALIFIER_LIMIT:
                phrase = phrase[:_QUALIFIER_LIMIT].rsplit(" ", 1)[0]
            return f" {prep} {phrase}"
    # «Ищут копирайтера с навыками Tilda» → «с навыками Tilda»
    m = re.search(r"\bс (навык\w*|опытом в|знанием) ([^.,:;!?()]{2,30})", first)
    if m:
        return f" с {m.group(1)} {m.group(2).split(' на ')[0].strip()}"
    return ""


_TIME_WORDS = {"день", "неделю", "месяц", "час", "сутки", "год", "смену", "выходные", "будни"}
_QUALIFIER_LIMIT = 60


# Должности, из которых собираем заголовок взамен кривого. Порядок не важен: берём ту, что раньше встретилась в тексте.
_ROLES = [
    (r"smm[- ]?специалист\w*", "SMM-специалист"),
    (r"специалист\w* по smm", "SMM-специалист"),
    (r"smm[- ]?менеджер\w*", "SMM-менеджер"),
    (r"контент[- ]?менеджер\w*", "Контент-менеджер"),
    (r"контент[- ]?маркетолог\w*", "Контент-маркетолог"),
    (r"(?:seo[- ])?копирайтер\w*", "Копирайтер"),
    (r"сценарист\w*", "Сценарист"),
    (r"редактор\w*", "Редактор"),
    (r"корректор\w*", "Корректор"),
    (r"автор\w* (?:текст|стат|пост)\w*", "Автор текстов"),
    (r"журналист\w*", "Журналист"),
    (r"райтер\w*", "Райтер"),
]
_PLACE_NOUNS = {"команду": "команда", "студию": "студия", "онлайн-школу": "онлайн-школа", "школу": "школа",
                "компанию": "компания", "редакцию": "редакция", "агентство": "агентство", "проект": "проект",
                "издательство": "издательство", "продакшн": "продакшн", "медиа": "медиа"}
TITLE_MAX = 70


def find_role(text):
    """Название должности, которое раньше всех встречается в тексте, или пустая строка. Ничего не придумываем."""
    low = norm(text)
    found = [(m.start(), name) for pattern, name in _ROLES for m in [re.search(rf"\b{pattern}", low)] if m]
    return min(found)[1] if found else ""


def _context(item):
    """Проект или компания из текста: «в команду Анфисы Чеховой» → «команда Анфисы Чеховой», «от продакшена X»."""
    head = " ".join(l.strip() for l in item.text.split("\n")[:4])
    m = re.search(r"\b[Вв] (" + "|".join(_PLACE_NOUNS) + r")\s+([«\"]?[A-ZА-ЯЁ][^,.:;!?()\n]{1,40}?)"
                  r"(?=\s+(?:ищ|нуж|требу|на\b|для\b|—)|[,.:;!?(]|$)", head)
    if m:
        return f"{_PLACE_NOUNS[m.group(1)]} {m.group(2).strip()}"
    m = re.search(r"\bот (?:продакшена|студии|агентства|компании)\s+(?:https?://)?([\w.-]+\.\w{2,}|[«\"][^»\"]{2,30}[»\"])", head, re.I)
    if m:
        return "продакшен " + m.group(1).rstrip("./")
    employer = tidy_title(employer_of(item)).split(" — ")[0] if employer_of(item) else ""
    return employer if len(employer) <= 40 else ""


def _bad_title(title):
    """Заголовок, который надо пересобрать из роли: «В солнечное воскресение…», «Ищут специалиста…», длинный, оборванный."""
    if re.match(r"(в|во|на|от)\s", title, re.I):
        return True
    if re.match(r"(ищем|ищут|ищу|требуется|требуются|нужен|нужна|нужны|в поисках)\b", title, re.I):
        return not find_role(title) or len(title) > TITLE_MAX
    return len(title) > TITLE_MAX or title.endswith("…")


def _without_greeting(title, item):
    """Заголовок без приветствия. Если приветствие и было всем заголовком («Доброго солнечного утра, дорогие»),
    берём фразу с «ищем/требуется», иначе следующую содержательную строку, тоже без приветствия."""
    stripped = strip_greeting(title).strip()
    if stripped == title.strip():
        return title
    if re.search(r"[A-Za-zА-Яа-яЁё]{3,}", stripped):
        return stripped[:1].upper() + stripped[1:]
    m = _SEEK.search(strip_contacts(item.text))  # без ссылок: точка в «hh.ru» обрывает фразу
    if m:
        return _clean_title(m.group(0).strip("[] "))
    for line in item.text.split("\n"):
        if _META_LINE.match(line):
            continue
        line =_clean_title(strip_greeting(line.strip("[] ")))
        if re.search(r"[A-Za-zА-Яа-яЁё]{3,}", line) and norm(line) not in norm(title):
            return line
    return title


def display_title(item):
    """Заголовок для сообщения (на отбор и дубли не влияет: там используется title_of)."""
    title = tidy_title(_without_greeting(title_of(item), item))
    first =tidy_title(_clean_title(next((l for l in item.text.split("\n") if l.strip()), "")))
    if item.part and first and len(first) <= 30 and re.search(r"[A-Za-zА-Яа-яЁё]{3,}", first):
        title = first  # пункт подборки: первая строка («24. #SMM») — это и есть роль
    if _bad_title(title) and find_role(title) and norm(title).startswith(norm(find_role(title))[:6]):
        short = _shorten_title(title)
        if short:
            return short
    if _bad_title(title):
        role = find_role(title) or find_role(item.text)
        if role:
            context = _context(item) or _title_tail(title)
            return f"{role} — {context}" if context else role
        return title
    if len(re.findall(r"[\w-]+", title)) <= 2 or ("/" in title and len(re.findall(r"[\w-]+", title)) <= 3):
        context = _context(item)
        if context and norm(context)[:12] not in norm(title):
            title += f" — {context}"
        else:
            extra = _qualifier(item, title)
            if len(extra) <= QUALIFIER_SHORT:
                title += extra
            elif "/" not in title:
                # «Копирайтер для маркетплейса и истории коллекций на основе комментариев» → «…и истории коллекций»
                title = _shorten_title(title + extra) or title
    return title


QUALIFIER_SHORT = 45


def _shorten_title(title):
    """«Копирайтер, тексты для Instagram, …, лендингов — RESTORADO» → «Копирайтер — RESTORADO»;
    «Копирайтер для маркетплейса и истории коллекций на основе комментариев» → «… и истории коллекций».
    Режем по запятым и предлогам, без многоточия. Пустая строка, если короче не выходит."""
    title = title.rstrip("…").strip()
    head, tail = (title.rsplit(" — ", 1) + [""])[:2] if " — " in title else (title, "")
    tail = tail if 2 <= len(tail) <= 30 else ""
    suffix = f" — {tail}" if tail else ""
    while len(head) + len(suffix) > TITLE_MAX:
        if "," in head:
            head = head.rsplit(",", 1)[0]
            continue
        m = re.search(r"^(.{8,}?)\s+(?:на|в|во|для|и|с|по)\s+[^ ]+(?:\s+[^ ]+)*$", head)
        cuts = [mm.start() for mm in re.finditer(r"\s(?:на|в|во|для|и|с|по)\s", head) if mm.start() >= 8]
        if not cuts:
            return ""
        head = head[: cuts[-1]]
    return head.strip(" ,—-") + suffix


def _title_tail(title):
    """Компания из самого заголовка: «… — RESTORADO», «… в Продюсерский центр Эда»."""
    title = title.rstrip("…").strip()
    if " — " in title:
        tail = title.rsplit(" — ", 1)[1].strip()
        if 2 <= len(tail) <= 30:
            return tail
    m = re.search(r"\s(?:в|во)\s+([«\"]?[A-ZА-ЯЁ][^,.:;!?]{2,})$", title)
    if m:
        tail = m.group(1)
        return tail if len(tail) <= 35 else tail[:35].rsplit(" ", 1)[0]
    return ""


def _who(item):
    title = display_title(item)
    employer = tidy_title(employer_of(item)).split(" — ")[0] if employer_of(item) else ""
    if employer and norm(employer)[:15] not in norm(title) and len(title) + len(employer) + 3 <= TITLE_LIMIT + 20:
        return f"{title} — {employer}"
    return title


def _labels(item, remote_words):
    labels = []
    pay = pay_of(item)
    if pay:
        labels.append(f"💰 {_abbr(pay)}")
    formats = work_format(item, remote_words)
    if pay and "за " in pay:
        formats = [f for f in formats if f != "проект"]  # «2 000 ₽ за проект» уже говорит про разовую оплату
    labels += formats
    city = city_only(item)
    if city:
        labels.append(f"📍 только {city}")
    if no_experience(item):
        labels.append("без опыта")
    else:
        years = experience_years(item)
        if years == 1:
            labels.append("опыт от года")
        elif years:
            labels.append(f"опыт от {years:g} лет".replace(".", ","))
    return " · ".join(labels)


def _contact_html(item):
    """Лучший способ отклика: @ник, потом анкета или ссылка, почта, телефон. Инстаграм не показываем."""
    order = {"nick": 0, "link": 1, "email": 2, "phone": 3}
    found = sorted((c for c in contacts_of(item) if c[1] in order), key=lambda c: order[c[1]])
    if not found:
        return ""
    key, kind, shown = found[0]
    if kind != "link":
        return escape(shown)
    tg_user = re.match(r"t\.me/([a-z]\w{3,})/?$", key)
    if tg_user:
        return escape("@" + tg_user.group(1))
    return f'<a href="{escape(shown, quote=True)}">{_link_label(key)}</a>'


def _link_label(key):
    """Подпись ссылки по её типу, чтобы было понятно, куда ведёт."""
    if re.search(r"forms\.gle|docs\.google\.com/forms|forms\.yandex|yandex\.ru/forms|typeform|tally\.so|anketa", key):
        return "анкета"
    if re.search(r"docs\.google\.com|forms?\.", key):
        return "форма"
    if "hh.ru" in key:
        return "hh.ru"
    if key.startswith("t.me/"):
        return "Telegram"
    if re.fullmatch(r"[^/]+/?", key):
        return "сайт компании"
    return key.split("/", 1)[0]  # домен: «himalayas.app»


def _contact_line(item):
    contact = _contact_html(item)
    if item.part and contact:
        return f"✉️ {contact}"
    if contact:
        return f"✉️ Откликнуться: {contact}"
    return "✉️ Контакт — в оригинальном посте (ссылка в заголовке)"


def format_vacancy(n, item, remote_words):
    title = escape(_abbr(_who(item)))
    lines = [f'<b>{n}. <a href="{item.url}">{title}</a></b>']
    summary = summary_of(item)
    if summary:
        lines.append(escape(_abbr(summary[0].upper() + summary[1:])))
    labels = _labels(item, remote_words)
    if labels:
        lines.append(escape(labels))
    lines.append(_contact_line(item))
    return "\n".join(lines)


def build_message(items, day, remote_words):
    head = f"<b>Вакансии на {day.day} {MONTHS[day.month - 1]}</b>"
    blocks = [format_vacancy(i + 1, item, remote_words) for i, item in enumerate(items)]
    return "\n\n".join([head, *blocks, escape(FOOTER)])
