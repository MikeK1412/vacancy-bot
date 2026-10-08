"""Дубли между каналами и память об отправленном (sent.json).

Одна и та же вакансия, если совпадает хотя бы одно:
- контакт для отклика (@ник, почта, ссылка на форму);
- конкретный заголовок (от трёх слов);
- текст похож сильно (DUPLICATE_THRESHOLD);
- текст похож умеренно (MARKS_THRESHOLD) и есть общая конкретная примета-число («30 сценариев»).
  Это для Текстодрома: контакт там скрыт за кнопкой, а текст переписан своими словами.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from textutils import contacts_of, norm, strip_contacts, tidy_title, title_of

MARKS_THRESHOLD = 0.45

# Слова из шаблонов постов, которые есть почти в каждой вакансии и не говорят о её сути.
_STOP = set("""
требования условия задачи обязанности откликнуться отклик оплата зарплата работодатель
удаленно удаленка удаленная удаленный формат график опыт работы работа работу компания
ищем ищут требуется нужен нужна вакансия вакансии будет будете нужно можно также если
месяц рублей тысяч занятость полная частичная проектная свободный тестовое задание
""".split())
_STEM = 5  # слова сравниваем по первым буквам, чтобы «роликов» и «ролики» совпадали


def signature(text):
    """Набор значимых слов текста (по первым буквам)."""
    words = re.findall(r"[a-zа-я0-9]{4,}", norm(strip_contacts(text)))
    return {w[:_STEM] for w in words if w not in _STOP}


def marks(text):
    """Конкретные числа из текста: «30 сценариев», «6–8 роликов». Годы и одиночные цифры не считаются."""
    # Суммы («100 000 ₽», «50к») приметами не считаем: у разных вакансий они часто совпадают.
    return set(re.findall(r"(?<![\d.,])(?<!\d\s)(\d{2,3})(?![\d.,]|\s?\d{3}|\s?(?:к\b|k\b|тыс|₽|руб|\$|€))",
                          strip_contacts(text)))


def similarity(a, b):
    """Доля общих слов от меньшего текста (0..1). Короткая перепечатка длинной вакансии тоже ловится."""
    if not a or not b:
        return 0.0
    small, large = sorted((len(a), len(b)))
    if small < 8:
        return len(a & b) / len(a | b)
    if large > 2.5 * small:
        # короткий пункт подборки почти целиком «находится» в любом длинном посте — считаем строже
        return len(a & b) / ((small + large) / 2)
    return len(a & b) / small


def title_key(item):
    """Заголовок для сравнения. Пустой, если он слишком общий («Копирайтер»): по нему склеивать нельзя."""
    words = re.findall(r"[a-zа-я0-9]+", norm(tidy_title(title_of(item))))
    return " ".join(words) if len(words) >= 3 else ""


def fingerprint(item):
    return {
        "words": signature(item.text),
        "title": title_key(item),
        "marks": marks(item.text),
        "contacts": {key for key, _, _ in contacts_of(item)},
    }


def is_same(a, b, threshold):
    """Одна и та же вакансия? a и b — результаты fingerprint(). Возвращает причину или пустую строку."""
    if a["contacts"] & b["contacts"]:
        return "контакт"
    if a["title"] and a["title"] == b["title"]:
        return "заголовок"
    sim = similarity(a["words"], b["words"])
    if sim >= threshold:
        return "текст"
    if sim >= MARKS_THRESHOLD and a["marks"] & b["marks"]:
        return "текст и приметы"
    return ""


def remove_duplicates(items, threshold, better):
    """Схлопывает одинаковые вакансии. Из группы остаётся лучшая по функции better(item) -> ключ сортировки.

    Возвращает (уникальные, список (выброшенная, оставленная, причина)).
    """
    ranked = sorted(items, key=better, reverse=True)
    kept, prints, dropped = [], [], []
    for item in ranked:
        fp = fingerprint(item)
        for k, kfp in zip(kept, prints):
            why = is_same(fp, kfp, threshold)
            if why:
                dropped.append((item, k, why))
                break
        else:
            kept.append(item)
            prints.append(fp)
    return kept, dropped


class SentStore:
    """sent.json: что уже отправляли. Храним ключ поста, дату и приметы для сравнения."""

    def __init__(self, path, keep_days):
        self.path = path
        self.entries = []
        if path.exists():
            self.entries = json.loads(path.read_text(encoding="utf-8"))
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        self.entries = [e for e in self.entries if datetime.fromisoformat(e["sent_at"]) >= cutoff]
        self._prints = [self._from_entry(e) for e in self.entries]
        self._keys = {e["key"] for e in self.entries}

    @staticmethod
    def _from_entry(e):
        return {
            "words": {w[:_STEM] for w in e["words"]},   # старые записи хранили слова целиком
            "title": e.get("title", ""),
            "marks": set(e.get("marks", [])),
            "contacts": set(e.get("contacts", [])),
        }

    def was_sent(self, item, threshold):
        if item.key in self._keys:
            return True
        fp = fingerprint(item)
        return any(is_same(fp, p, threshold) for p in self._prints)

    def add(self, item):
        fp = fingerprint(item)
        self.entries.append({
            "key": item.key,
            "url": item.url,
            "title": fp["title"],
            "contacts": sorted(fp["contacts"]),
            "marks": sorted(fp["marks"]),
            "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "words": sorted(fp["words"]),
        })
        self._prints.append(fp)
        self._keys.add(item.key)

    def save(self):
        self.path.write_text(json.dumps(self.entries, ensure_ascii=False, indent=1), encoding="utf-8")
