"""Сообщение для группы (Telegram HTML)."""
import re
from html import escape

from textutils import TITLE_LIMIT, employer_of, norm, pay_of, summary_of, tidy_title, title_of


def _abbr(text):
    """Аббревиатуры заглавными: «seo-статьи» → «SEO-статьи»."""
    return re.sub(r"\bseo\b", "SEO", text, flags=re.I)


def _who(item):
    title = tidy_title(title_of(item))
    employer = tidy_title(employer_of(item)) if employer_of(item) else ""
    if employer and norm(employer)[:15] not in norm(title) and len(title) + len(employer) + 3 <= TITLE_LIMIT + 20:
        return f"{title} — {employer}"
    return title


def format_vacancy(n, item):
    lines = [f"<b>{n}. {escape(_abbr(_who(item)))}</b>"]
    summary = summary_of(item)
    if summary:
        lines.append(escape(_abbr(summary[0].upper() + summary[1:])))
    pay = pay_of(item)
    if pay:
        lines.append(f"💰 Оплата: {escape(_abbr(pay))}")
    lines.append(f'🔗 <a href="{item.url}">Вакансия в канале @{escape(item.channel)}</a>')
    return "\n".join(lines)


def build_message(items):
    head = "<b>Вакансии для копирайтеров на удалёнке</b>"
    blocks = [format_vacancy(i + 1, item) for i, item in enumerate(items)]
    tail = "Откликайтесь по ссылке на пост: контакты работодателя там."
    return "\n\n".join([head, *blocks, tail])
