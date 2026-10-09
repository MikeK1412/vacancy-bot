"""Отбор вакансий: подходит или нет.

Единственная точка, которую вызывает main.py: check(item) -> Verdict.
Сейчас решение по спискам слов из keywords.txt. Когда появится ключ API нейросети,
рядом добавляется своя функция с тем же входом и выходом (например check_ai),
и в config.SELECTOR выбирается, какую использовать. Остальной код не меняется.
"""
import re
from dataclasses import dataclass

import config
from textutils import contact_button, contacts_of, experience_years, find_any, latin_share, load_keywords, norm, title_of


@dataclass
class Verdict:
    ok: bool
    reason: str  # почему отсеяна или по какому слову прошла (для отладки)


_keywords = None


def keywords():
    global _keywords
    if _keywords is None:
        _keywords = load_keywords(config.KEYWORDS_FILE)
    return _keywords


def required_language(text, kw):
    """Иностранный язык, который нужен обязательно. Строки с «плюсом», «желательно» и т.п. не считаются."""
    for line in re.split(r"[\n;]", text):
        lang = find_any(line, kw.get("иностранный язык", []))
        if lang and not find_any(line, kw.get("язык не обязателен", [])):
            return lang
    return None


def is_smm(item):
    return bool(find_any(norm(title_of(item)), keywords().get("smm и контент", [])))


def priority(item):
    """1 — текстовые роли (копирайтер, редактор, автор, сценарист), 0 — SMM, контент-менеджеры и прочее."""
    title = norm(title_of(item))
    if is_smm(item):
        return 0
    return 1 if find_any(title, keywords().get("текстовые роли", [])) else 0


# --- «Не вакансия»: статьи, советы, подборки ---------------------------------
# Решаем по совокупности признаков найма, а не по одному слову: настоящая вакансия с фразой «в кризис»
# или «как мы работаем» в тексте не пострадает, если в ней есть работодатель, задачи, условия и контакт.

_HIRING = re.compile(r"\b(ищем|ищет|ищут|ищу|требуется|требуются|в поисках|приглашаем|нужен|нужна|нужны|открыта вакансия"
                     r"|работодатель\s*:|компания\s*:|где\s*:)", re.I)
_DUTIES = re.compile(r"(задачи|обязанности|что (?:нужно|предстоит|будет нужно) делать|чем (?:предстоит|нужно) заниматься"
                     r"|требования|кого (?:мы )?ищ|ожидани|что (?:мы )?ждем|вам предстоит)\s*:?", re.I)
_TERMS = re.compile(r"(условия|оплата|зарплата|з/п|\bзп\b|гонорар|ставка|оклад|график|формат работы|занятость"
                    r"|удален|удалён|₽|руб|тыс\b)", re.I)


def hiring_signals(item):
    """Какие из четырёх признаков найма есть в посте: работодатель, задачи, условия, контакт."""
    text = item.text
    return {
        "работодатель": bool(_HIRING.search(text)),
        "задачи": bool(_DUTIES.search(text)),
        "условия": bool(_TERMS.search(norm(text))),
        "контакт": bool(contacts_of(item)) or contact_button(item),
    }


def is_not_vacancy(item, kw):
    """Причина, если пост не вакансия (статья, совет, подборка), иначе пустая строка."""
    s = hiring_signals(item)
    title = norm(title_of(item))
    if not s["контакт"] and not s["условия"]:
        return "нет ни контакта, ни условий"
    advice = find_any(title, kw.get("не вакансия: заголовок", []))
    if advice and sum(s.values()) < 3:
        return f"статья или совет: «{advice}»"
    if (title.endswith("?") or title.startswith("как ")) and not s["контакт"]:
        return "заголовок-вопрос без контакта"
    return ""


def editor_only(item, kw):
    """Заголовок про редактора или корректора, а в тексте нет копирайтинга: это не наша вакансия."""
    title = norm(title_of(item))
    if not re.search(r"редактор|корректор", title):
        return False
    # «Копирайтер-редактор», «Редактор / копирайтер», «SMM-редактор», «Контент-редактор», «Редактор / журналист» — пишущие роли
    if re.search(r"копирайт|автор|райтер|writer|сценар|журналист|smm|смм|контент", title):
        return False
    return not find_any(norm(item.text), kw.get("копирайтинг в тексте", []))


def check_keywords(item):
    kw = keywords()
    text = norm(item.text)
    title = norm(title_of(item))
    full = norm(item.context) + "\n" + text  # шапка дайджеста тоже говорит про удалёнку

    junk = find_any(text, kw.get("мусор", []))
    if junk:
        return Verdict(False, f"мусор: {junk}")
    ad = find_any(text, kw.get("реклама каналов", []))
    if ad:
        return Verdict(False, f"реклама канала: {ad}")
    banned = find_any(text, kw.get("запрещённая соцсеть", []))
    if banned:
        return Verdict(False, f"инстаграм: {banned}")
    not_vacancy = is_not_vacancy(item, kw)
    if not_vacancy:
        return Verdict(False, f"не вакансия: {not_vacancy}")
    foreign = required_language(text, kw)
    if foreign:
        return Verdict(False, f"иностранный язык: {foreign}")
    if len(text) > 150 and latin_share(text) > 0.5:
        return Verdict(False, "иностранный язык: текст не на русском")
    off_topic = find_any(title, kw.get("не тема", []))
    if off_topic:
        return Verdict(False, f"не тема: {off_topic}")
    topic = find_any(title, kw.get("тема в заголовке", [])) or find_any(text, kw.get("тема в тексте", []))
    if not topic:
        return Verdict(False, "не тема: нет слов про тексты")
    if editor_only(item, kw):
        return Verdict(False, "редактор, не копирайтер")
    if is_smm(item):
        shooting = find_any(text, kw.get("smm: съёмки и выезды", []))
        if shooting:
            return Verdict(False, f"smm со съёмками: {shooting}")
    hard_office = find_any(full, kw.get("не удалёнка", []))
    if hard_office:
        return Verdict(False, f"не удалёнка: {hard_office}")
    remote = find_any(full, kw.get("удалёнка", []))
    if not remote:
        office = find_any(full, kw.get("офис", []))
        if office:
            return Verdict(False, f"офис: {office}")
        if item.channel not in config.TEXT_CHANNELS:
            return Verdict(False, "удалёнка не указана")
    years = experience_years(item)
    if years is not None and years >= config.MAX_EXPERIENCE_YEARS:
        return Verdict(False, f"опыт от {years:g} лет")
    contacts = contacts_of(item)
    if contacts and all(kind == "instagram" for _, kind, _ in contacts):
        return Verdict(False, "инстаграм: отклик только там")
    if not contacts and item.channel not in config.BUTTON_CONTACT_CHANNELS:
        return Verdict(False, "нет контакта для отклика")
    return Verdict(True, f"тема «{topic}», " + (f"удалёнка «{remote}»" if remote else "формат не указан (текстовый канал)"))


def check(item):
    if config.SELECTOR == "keywords":
        return check_keywords(item)
    raise ValueError(f"Неизвестный способ отбора: {config.SELECTOR}")
