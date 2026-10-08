"""Отбор вакансий: подходит или нет.

Единственная точка, которую вызывает main.py: check(item) -> Verdict.
Сейчас решение по спискам слов из keywords.txt. Когда появится ключ API нейросети,
рядом добавляется своя функция с тем же входом и выходом (например check_ai),
и в config.SELECTOR выбирается, какую использовать. Остальной код не меняется.
"""
import re
from dataclasses import dataclass

import config
from textutils import find_any, latin_share, load_keywords, norm, title_of


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


def check_keywords(item):
    kw = keywords()
    text = norm(item.text)
    title = norm(title_of(item))
    full = norm(item.context) + "\n" + text  # шапка дайджеста тоже говорит про удалёнку

    junk = find_any(text, kw.get("мусор", []))
    if junk:
        return Verdict(False, f"мусор: {junk}")
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
        return Verdict(True, f"тема «{topic}», формат не указан (текстовый канал)")
    return Verdict(True, f"тема «{topic}», удалёнка «{remote}»")


def check(item):
    if config.SELECTOR == "keywords":
        return check_keywords(item)
    raise ValueError(f"Неизвестный способ отбора: {config.SELECTOR}")
