"""Сообщение для группы (Telegram HTML).

Вакансия:
    1. Заголовок — работодатель        (жирный, ссылка на пост)
    Суть: задачи и главное требование, до 280 знаков
    💰 оплата · удалёнка · частичная · без опыта   (только то, что нашлось)
    ✉️ контакт
"""
import re
from html import escape

from textutils import (TITLE_LIMIT, contacts_of, digest_number, employer_of, experience_years, no_experience, norm,
                       pay_of, summary_of, tidy_title, title_of, work_format)

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
    if m and not re.match(r"(?:мы|я|ищем|ищу|компания|команда)\b", m.group(1), re.I):
        who = m.group(1)
        return " — " + (who[:1].lower() + who[1:] if who[1:2].islower() else who)  # «ООО» не трогаем
    # «…копирайтера в команду для проектов экспертов и продюсеров» → «для проектов экспертов и продюсеров»
    for prep in ("для", "в", "во"):
        for m in re.finditer(rf"\b{prep}\s+([^.,:;!?()]{{3,80}})", first):
            phrase = m.group(1).strip()
            if prep != "для":
                phrase = re.split(r"\s+(?:для|и нужно|нужно|которы\w*|чтобы)\b", phrase)[0]
            low = phrase.lower()
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


def _who(item):
    title = tidy_title(title_of(item))
    if "/" not in title and len(re.findall(r"[\w-]+", title)) <= 2:  # общий заголовок из одной должности
        title += _qualifier(item, title)
    employer = tidy_title(employer_of(item)) if employer_of(item) else ""
    if employer and norm(employer)[:15] not in norm(title) and len(title) + len(employer) + 3 <= TITLE_LIMIT + 20:
        return f"{title} — {employer}"
    return title


def _labels(item, remote_words):
    labels = []
    pay = pay_of(item)
    if pay:
        labels.append(f"💰 {_abbr(pay)}")
    labels += work_format(item, remote_words)
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
        return f"✉️ {contact} · из подборки, пункт {digest_number(item)}"
    if contact:
        return f"✉️ Откликнуться: {contact}"
    return "✉️ Контакт по кнопке под постом"


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
