"""Дубли между каналами и память об отправленном (sent.json)."""
import json
import re
from datetime import datetime, timedelta, timezone

from textutils import norm, strip_contacts, tidy_title, title_of

# Слова из шаблонов постов, которые есть почти в каждой вакансии и не говорят о её сути.
_STOP = set("""
требования условия задачи обязанности откликнуться отклик оплата зарплата работодатель
удаленно удаленка удаленная удаленный формат график опыт работы работа работу компания
ищем ищут требуется нужен нужна вакансия вакансии будет будете нужно можно также если
месяц рублей тысяч занятость полная частичная проектная свободный тестовое задание
""".split())


def signature(text):
    """Набор значимых слов текста."""
    words = re.findall(r"[a-zа-я0-9]{4,}", norm(strip_contacts(text)))
    return {w for w in words if w not in _STOP}


def similarity(a, b):
    """Доля общих слов от меньшего текста (0..1). Короткая перепечатка длинной вакансии тоже ловится."""
    if not a or not b:
        return 0.0
    small = min(len(a), len(b))
    if small < 8:
        return len(a & b) / len(a | b)
    return len(a & b) / small


def title_key(item):
    """Заголовок для сравнения. Пустой, если он слишком общий («Копирайтер»): по нему склеивать нельзя."""
    words = re.findall(r"[a-zа-я0-9]+", norm(tidy_title(title_of(item))))
    return " ".join(words) if len(words) >= 3 else ""


def is_same(sig_a, title_a, sig_b, title_b, threshold):
    """Одна и та же вакансия: похожий текст или одинаковый конкретный заголовок (каналы переписывают текст своими словами)."""
    return similarity(sig_a, sig_b) >= threshold or bool(title_a and title_a == title_b)


def remove_duplicates(items, threshold, better):
    """Схлопывает похожие вакансии. Из группы остаётся лучшая по функции better(item) -> ключ сортировки.

    Возвращает (уникальные, список пар (выброшенная, оставленная)).
    """
    ranked = sorted(items, key=better, reverse=True)
    kept, dropped, marks = [], [], []
    for item in ranked:
        sig, title = signature(item.text), title_key(item)
        twin = next((k for k, (s, t) in zip(kept, marks) if is_same(sig, title, s, t, threshold)), None)
        if twin is None:
            kept.append(item)
            marks.append((sig, title))
        else:
            dropped.append((item, twin))
    return kept, dropped


class SentStore:
    """sent.json: что уже отправляли. Храним ключ поста, дату и набор слов для сравнения похожести."""

    def __init__(self, path, keep_days):
        self.path = path
        self.keep_days = keep_days
        self.entries = []
        if path.exists():
            self.entries = json.loads(path.read_text(encoding="utf-8"))
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        self.entries = [e for e in self.entries if datetime.fromisoformat(e["sent_at"]) >= cutoff]
        self._marks = [(set(e["words"]), e.get("title", "")) for e in self.entries]
        self._keys = {e["key"] for e in self.entries}

    def was_sent(self, item, threshold):
        if item.key in self._keys:
            return True
        sig, title = signature(item.text), title_key(item)
        return any(is_same(sig, title, s, t, threshold) for s, t in self._marks)

    def add(self, item):
        sig, title = signature(item.text), title_key(item)
        self.entries.append({
            "key": item.key,
            "url": item.url,
            "title": title,
            "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "words": sorted(sig),
        })
        self._marks.append((sig, title))
        self._keys.add(item.key)

    def save(self):
        self.path.write_text(json.dumps(self.entries, ensure_ascii=False, indent=1), encoding="utf-8")
