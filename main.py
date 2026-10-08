"""Парсер вакансий: собирает посты из каналов, отбирает до пяти вакансий и отправляет в группу.

    python main.py --dry-run          печать сообщения в консоль, sent.json не меняется
    python main.py --dry-run --debug  плюс список прошедших, отсеянных и дублей
    python main.py                    отправка в группу (нужны BOT_TOKEN и CHAT_ID в .env)
"""
import argparse
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import config
import selector
from collector import collect
from dedup import SentStore, remove_duplicates
from formatter import build_message
from tg import TelegramError, send_message
from textutils import pay_of, tidy_title, title_of

MSK = timezone(timedelta(hours=config.TIMEZONE_OFFSET_HOURS))


def has_pay(item):
    return bool(pay_of(item))


def rank_key(item):
    """Сначала текстовые роли, потом SMM и контент. Внутри группы: с оплатой за последние
    PAID_PRIORITY_DAYS дней, потом остальные; дальше по свежести."""
    recent = item.date >= datetime.now(timezone.utc) - timedelta(days=config.PAID_PRIORITY_DAYS)
    return (selector.priority(item), recent and has_pay(item), item.date)


def choose(items):
    """До MAX_VACANCIES лучших, не больше MAX_PER_CHANNEL из одного канала."""
    chosen, per_channel = [], Counter()
    for item in sorted(items, key=rank_key, reverse=True):
        if per_channel[item.channel] >= config.MAX_PER_CHANNEL:
            continue
        chosen.append(item)
        per_channel[item.channel] += 1
        if len(chosen) == config.MAX_VACANCIES:
            break
    return chosen


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="не отправлять, напечатать сообщение")
    ap.add_argument("--debug", action="store_true", help="показать, что прошло отбор и что отсеяно")
    args = ap.parse_args()

    token, chat_id = config.telegram_settings()
    if not args.dry_run and not (token and chat_id):
        sys.exit("Нет BOT_TOKEN или CHAT_ID. Заполните .env (образец: .env.example) или запустите с --dry-run.")

    tails = selector.keywords().get("хвосты", [])
    print(f"Сбор постов за {config.DAYS_BACK} дн. из {len(config.CHANNELS)} каналов…")
    items, stats = collect(config.CHANNELS, config.DAYS_BACK, tails)

    passed, reasons, passed_by_channel = [], Counter(), Counter()
    for item in items:
        verdict = selector.check(item)
        if verdict.ok:
            passed.append(item)
            passed_by_channel[item.channel] += 1
            item.extra["reason"] = verdict.reason
        else:
            reasons[verdict.reason.split(":")[0]] += 1
            item.extra["reason"] = verdict.reason

    print("\nКанал                   постов  вакансий  прошло")
    for ch in config.CHANNELS:
        s = stats.get(ch)
        if isinstance(s, tuple):
            print(f"{ch:<22} {s[0]:>6} {s[1]:>9} {passed_by_channel[ch]:>7}")
        else:
            print(f"{ch:<22} {s}")
    print(f"Итого: постов {sum(s[0] for s in stats.values() if isinstance(s, tuple))}, "
          f"вакансий после нарезки дайджестов {len(items)}, прошло отбор {len(passed)}")
    print("Отсеяно: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common()))

    unique, dupes = remove_duplicates(passed, config.DUPLICATE_THRESHOLD,
                                      better=lambda i: (has_pay(i), i.date))
    store = SentStore(config.SENT_FILE, config.SENT_KEEP_DAYS)
    # Вакансия считается отправленной, если отправлялась любая её копия из других каналов.
    copies = {i.key: [i] for i in unique}
    for d, k, _ in dupes:
        copies[k.key].append(d)
    fresh = [i for i in unique
             if not any(store.was_sent(c, config.DUPLICATE_THRESHOLD) for c in copies[i.key])]
    print(f"Дублей между постами убрано: {len(dupes)}; уже отправлялись раньше: {len(unique) - len(fresh)}; "
          f"кандидатов: {len(fresh)}")

    chosen = choose(fresh)

    if args.debug:
        print("\n--- Прошли отбор ---")
        for i in sorted(passed, key=rank_key, reverse=True):
            print(f"  {i.date.astimezone(MSK):%d.%m %H:%M} {i.url}{'#' + str(i.part) if i.part else ''}"
                  f" | {tidy_title(title_of(i))} | {i.extra['reason']}")
        print("\n--- Отсеяны не по теме: мусор, офис, нет удалёнки ---")
        for i in items:
            if not i.extra["reason"].startswith(("не тема", "тема")):
                print(f"  {i.key} | {tidy_title(title_of(i))} | {i.extra['reason']}")
        print("\n--- Дубли (выброшено → оставлено) ---")
        for d, k, why in dupes:
            print(f"  {d.key} → {k.key} ({why}) | {tidy_title(title_of(d))}")

    if not chosen:
        print("\nПодходящих новых вакансий нет, сообщение не отправляется.")
        return

    today = datetime.now(MSK).date()
    message = build_message(chosen, today, selector.keywords().get("удалёнка", []))
    if args.dry_run:
        print(f"\n=== Сообщение ({len(chosen)} вак., {len(message)} знаков) ===\n")
        print(message)
        print("\n(--dry-run: ничего не отправлено, sent.json не изменён)")
        return

    print(f"\n=== Отправляется ({len(chosen)} вак.) ===\n{message}")
    try:
        send_message(token, chat_id, message)
    except TelegramError as e:
        sys.exit(f"Telegram не принял сообщение: {e}")
    for item in chosen:
        store.add(item)
    store.save()
    print(f"\nОтправлено {len(chosen)} вакансий, sent.json обновлён.")


if __name__ == "__main__":
    main()
