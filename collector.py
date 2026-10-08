"""Сбор постов из публичных телеграм-каналов через веб-превью t.me/s/<канал>.

Аккаунт Telegram не нужен. Страница отдаёт ~20 последних постов, дальше листаем
параметром ?before=<id самого старого поста>.

Отдельный запуск выгружает посты в текстовые файлы (для анализа каналов):
    python collector.py --days 30 --out выгрузка rueventjob textodromo
"""
import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (vacancy-digest bot)"}
MAX_PAGES = 30


@dataclass
class Post:
    channel: str
    post_id: int
    date: datetime
    text: str
    context: str = ""       # шапка дайджеста, из которого вырезан пункт (например «(#Удаленка) Требуются...»)
    part: int = 0           # номер пункта в дайджесте, 0 для обычного поста
    extra: dict = field(default_factory=dict)

    @property
    def url(self):
        return f"https://t.me/{self.channel}/{self.post_id}"

    @property
    def key(self):
        return f"{self.channel}/{self.post_id}" + (f"#{self.part}" if self.part else "")


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.posts = []
        self.cur = None
        self.depth = 0
        self.in_text = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if tag == "div" and "tgme_widget_message " in cls + " " and a.get("data-post"):
            self.cur = {"id": int(a["data-post"].split("/")[-1]), "date": None, "text": "",
                        "service": "service_message" in cls}  # «канал закрепил сообщение» и т.п.
            self.posts.append(self.cur)
        if self.cur is None:
            return
        if tag == "time" and a.get("datetime") and self.cur["date"] is None:
            self.cur["date"] = a["datetime"]
        if self.in_text:
            if tag == "div":
                self.depth += 1
            if tag == "br":
                self.cur["text"] += "\n"
        elif tag == "div" and "tgme_widget_message_text" in cls:
            self.in_text = True
            self.depth = 1
            if self.cur["text"]:
                self.cur["text"] += "\n"

    def handle_startendtag(self, tag, attrs):
        if self.in_text and tag == "br":
            self.cur["text"] += "\n"

    def handle_endtag(self, tag):
        if self.in_text and tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.in_text = False

    def handle_data(self, data):
        if self.in_text and self.cur is not None:
            self.cur["text"] += data


def _get(session, url, tries=3):
    for attempt in range(tries):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.text
        except requests.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def fetch_channel(channel, since, session=None):
    """Все посты канала с текстом, опубликованные не раньше since (datetime в UTC)."""
    session = session or requests.Session()
    found = {}
    url = f"https://t.me/s/{channel}"
    for _ in range(MAX_PAGES):
        parser = _PageParser()
        parser.feed(_get(session, url))
        if not parser.posts:
            break
        for p in parser.posts:
            found[p["id"]] = p
        oldest = min(parser.posts, key=lambda p: p["id"])
        if oldest["date"] and datetime.fromisoformat(oldest["date"]) < since:
            break
        url = f"https://t.me/s/{channel}?before={oldest['id']}"
        time.sleep(0.7)
    posts = []
    for p in sorted(found.values(), key=lambda p: p["id"]):
        if not p["date"] or p["service"]:
            continue
        date = datetime.fromisoformat(p["date"])
        text = re.sub(r"\n{3,}", "\n\n", p["text"].strip())
        if date >= since and text:
            posts.append(Post(channel, p["id"], date, text))
    return posts


# --- подвалы и дайджесты -------------------------------------------------

def cut_tail(text, tails):
    """Обрезает рекламный подвал: всё, начиная со строки, где встретился любой маркер из tails."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        low = line.lower()
        if i > 0 and any(t in low for t in tails):
            return "\n".join(lines[:i]).strip()
    return text


_NUMBERED_ITEM = re.compile(r"^\s*\d{1,2}\.\s*#\S")      # «12. #Копирайтер» (Удаленка)
_WAVY_SEPARATOR = re.compile(r"^\s*(?:〰️?){3,}\s*$")      # «〰️〰️〰️» (Текстодром)


def split_digest(post):
    """Режет дайджест на отдельные вакансии. Обычный пост возвращает как есть."""
    lines = post.text.split("\n")
    starts = [i for i, l in enumerate(lines) if _NUMBERED_ITEM.match(l)]
    if len(starts) >= 2:
        header = "\n".join(lines[: starts[0]]).strip()
        bounds = starts + [len(lines)]
        chunks = ["\n".join(lines[a:b]).strip() for a, b in zip(bounds, bounds[1:])]
    else:
        seps = [i for i, l in enumerate(lines) if _WAVY_SEPARATOR.match(l)]
        if len(seps) < 2:
            return [post]
        bounds = [-1] + seps + [len(lines)]
        parts = ["\n".join(lines[a + 1:b]).strip() for a, b in zip(bounds, bounds[1:])]
        header, chunks = parts[0], parts[1:]
    items = []
    for n, chunk in enumerate(c for c in chunks if c):
        items.append(Post(post.channel, post.post_id, post.date, chunk, context=header, part=n + 1))
    return items or [post]


def collect(channels, days, tails, log=print):
    """Посты всех каналов за days дней: подвалы срезаны, дайджесты разрезаны.

    Возвращает (items, stats), stats[канал] = (постов, вакансий после нарезки) или текст ошибки.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    session = requests.Session()
    items, stats = [], {}
    for ch in channels:
        try:
            posts = fetch_channel(ch, since, session)
        except requests.RequestException as e:
            stats[ch] = f"ошибка: {e.__class__.__name__}"
            log(f"  {ch}: не удалось скачать ({e})")
            continue
        chunks = []
        for p in posts:
            p.text = cut_tail(p.text, tails)
            for item in split_digest(p):
                item.text = cut_tail(item.text, tails)
                if item.text:
                    chunks.append(item)
        stats[ch] = (len(posts), len(chunks))
        items.extend(chunks)
    return items, stats


def _dump(argv):
    ap = argparse.ArgumentParser(description="Выгрузка постов каналов в текстовые файлы")
    ap.add_argument("channels", nargs="+")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default="выгрузка")
    args = ap.parse_args(argv)
    from pathlib import Path
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    for ch in args.channels:
        posts = fetch_channel(ch, since)
        with open(out / f"{ch}.txt", "w", encoding="utf-8") as f:
            f.write(f"# {ch}: {len(posts)} posts since {since.date()}\n\n")
            for p in posts:
                f.write(f"=== #{p.post_id} {p.date.isoformat()[:16]}\n{p.text}\n\n")
        print(ch, len(posts))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    _dump(sys.argv[1:])
