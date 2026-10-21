"""Отбор вакансий: подходит или нет.

Единственная точка, которую вызывает main.py: check(item) -> Verdict.
Сейчас решение по спискам слов из keywords.txt. Когда появится ключ API нейросети,
рядом добавляется своя функция с тем же входом и выходом (например check_ai),
и в config.SELECTOR выбирается, какую использовать. Остальной код не меняется.
"""
import re
from dataclasses import dataclass

import config
from textutils import (_words_regex, city_only, contact_button, contacts_of, experience_years, find_any, latin_share,
                       greeting_title, load_keywords, norm, title_of)


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


_INSTAGRAM = re.compile(r"instagram|инстаграм|\bинст[аыуе]?\b|\binsta\b", re.I)


def instagram_problem(item, kw):
    """Правило Instagram: причина, если откликнуться можно только через Instagram или вакансия целиком про него.

    Instagram как площадка для текстов и сноска «запрещённая в РФ соцсеть» не мешают, если есть другой контакт.
    """
    contacts = contacts_of(item)
    other = [c for c in contacts if c[1] != "instagram"] or contact_button(item)
    direct = find_any(norm(item.text), kw.get("instagram: отклик в директ", []))
    if not other and (direct or any(c[1] == "instagram" for c in contacts)):
        return "отклик только через Instagram"
    title = norm(title_of(item))
    if _INSTAGRAM.search(title) and not find_any(title, kw.get("instagram: другие площадки", [])):
        return "вакансия целиком про Instagram"
    return ""


def bot_only_contact(item, kw):
    """Единственный способ отклика — бот (ник или ссылка на …bot), и это не известный бот канала с контактами."""
    contacts = [c for c in contacts_of(item) if c[1] != "instagram"]
    if not contacts or contact_button(item):
        return False
    known = kw.get("боты для отклика", [])

    def is_bot(key):
        name = key.split("?")[0].rstrip("/").split("/")[-1].lstrip("@")
        return name.endswith("bot") and name not in known

    return all(is_bot(key) for key, _, _ in contacts)


def is_ad(item, kw):
    """Реклама курса или бота: по совокупности рекламных признаков и при отсутствии работодателя и условий найма."""
    text = norm(item.text)
    hits = {p for p in kw.get("реклама курсов", []) if p in text}
    raw_title = title_of(item)
    letters = [c for c in raw_title if c.isalpha()]
    shout = "!" in raw_title and letters and sum(c.isupper() for c in letters) / len(letters) > 0.7
    score = len(hits) + (1 if shout else 0)
    s = hiring_signals(item)
    return score >= 2 and not s["работодатель"] and not s["условия"]


def is_service_ad(item, kw):
    """Реклама сервиса («AI-копирайтер на базе Claude, бот в Telegram, без VPN»): минимум два рекламных признака
    (названия моделей считаются за один) и нет условий найма и перечня задач. Работодателя не требуем:
    «НейроПеро ищет свежие данные» совпадает с «ищет», но вакансией не является."""
    text = norm(item.text)
    hits = {p for p in kw.get("реклама сервисов", []) if p in text}
    if find_any(text, kw.get("реклама сервисов: модели", [])):
        hits.add("модель")
    s = hiring_signals(item)
    return len(hits) >= 2 and not s["условия"] and not s["задачи"]


def adult_content(item, kw):
    """Фраза из [18+], если контент для взрослых. Требование к возрасту кандидата («возраст 18+», «• 18+») не считается."""
    skip = kw.get("18+: не считать строку", [])
    for line in norm(item.text).split("\n"):
        if find_any(line, skip) or len(line.strip(" •✓✔-–—*·	")) <= 8:
            continue  # «возраст 18+», «✓ Гражданство РФ, 18+», пункт списка «• 18+»
        # «18+, грамотная речь»: «18+» в начале строки перед запятой — перечень требований
        line = re.sub(r"^[\W]*18\+\s*[,;]", "", line)
        hit = find_any(line, kw.get("18+", []))
        if hit:
            return hit
    return ""


def not_about_texts(item, kw):
    """Слово из [не про тексты: заголовок] (SMM, CRM), если в заголовке нет ни одного слова из [тексты в заголовке]."""
    title = norm(title_of(item))
    hit = find_any(title, kw.get("не про тексты: заголовок", []))
    if hit and not find_any(title, kw.get("тексты в заголовке", [])):
        return hit
    return ""


def greeting_without_role(item, kw):
    """Первая строка — одно приветствие, а в заголовке (после замены на фразу «ищем…») нет ни одной профессии."""
    if not greeting_title(item):
        return False
    roles = kw.get("тема в заголовке", []) + kw.get("текстовые роли", []) + kw.get("smm и контент", [])
    return not find_any(norm(title_of(item)), roles)


def is_not_vacancy(item, kw):
    """Причина, если пост не вакансия (статья, совет, подборка, реклама курса или бота), иначе пустая строка."""
    if bot_only_contact(item, kw):
        return "отклик только через бота"
    if is_ad(item, kw):
        return "реклама курса или бота"
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


# --- очная работа, жёсткий график, старшие позиции ----------------------------

# «10:00–19:00», «с 09:00 до 18:00», «5/2 с 10:00» — время с минутами
_CLOCK = re.compile(r"(?<!\d)\d{1,2}:\d{2}\s*(?:-|–|—|до)\s*\d{1,2}:\d{2}"
                    r"|(?<!\w)с\s*\d{1,2}:\d{2}\s*(?:-|–|—|до)\s*\d{1,2}(?::\d{2})?(?!\d)"
                    r"|5\s*/\s*2[^\n.;]{0,20}?(?<!\w)с\s*\d{1,2}:\d{2}")
# «с 9 до 18» — без минут, только правдоподобные часы и не «с 1 до 3 месяцев»
_BARE_HOURS = re.compile(r"(?<!\w)с\s*(\d{1,2})\s*(?:до|-|–|—)\s*(\d{1,2})(?![\d.,:])"
                         r"(?!\s*(?:тыс|к\b|k\b|%|₽|\$|руб|р\b|мес|лет|год|дн|знак|шт|слов|чел|раз|мин|сек|постов|статей|текст))")
# так пишут про удалёнку: «на связи с 10 до 19 по МСК»
_ONLINE_HOURS = re.compile(r"на связи|онлайн|в сети|мск|по москв|часов\w* пояс")


def hard_schedule(text):
    """Жёсткий рабочий график («с 9 до 18», «5/2 с 10:00») — признак офиса, если формат не указан."""
    for line in re.split(r"[\n;]", norm(text)):
        if _ONLINE_HOURS.search(line):
            continue
        m = _CLOCK.search(line)
        if m:
            return m.group(0).strip()
        for m in _BARE_HOURS.finditer(line):
            if 6 <= int(m.group(1)) <= 12 and 15 <= int(m.group(2)) <= 22:
                return m.group(0).strip()
    return ""


_NEGATED = re.compile(r"(?<!\w)(?:без|не|нет|никаких|ни)\s+(?:\w+\s+){0,2}$")
_NEGATED_AFTER = re.compile(r"^\w*(?:\s+\w+){0,2}\s+не\s+(?:потребуется|нужно|нужен|нужна|нужны|требуется|обязательн|придется|надо)")
_CHOICE = re.compile(r"(?<!\w)или(?!\w)|на выбор|по желанию|по возможности|при желании|можно")


def onsite(text, kw):
    """Фраза очной работы из [очная работа] или пустая строка.

    Не считаются: отрицание («без выездов», «не нужно ездить в офис», «присутствовать на них не потребуется») и выбор вместе с удалёнкой
    в той же строке («Удалёнка или офис в Москве: работайте, где удобно»).
    """
    for line in re.split(r"[\n;]", text):
        for p in kw.get("очная работа", []):
            for m in _words_regex(p).finditer(line):
                if _NEGATED.search(line[max(0, m.start() - 40):m.start()]) or _NEGATED_AFTER.search(line[m.end():]):
                    continue
                if _CHOICE.search(line) and find_any(line, kw.get("удалёнка", [])):
                    continue
                return p
    return ""


# «ассистент руководителя», «помощник главного редактора», «для руководителя» — не старшая позиция
_NOT_SENIOR = re.compile(r"(?<!\w)(?:ассистент\w*|помощни\w*|для|при|у|от|с)\s+$")


def senior_title(item, kw):
    """Слово старшей позиции в заголовке («старший», «главный редактор», «head»), иначе пустая строка."""
    title = norm(title_of(item))
    for p in kw.get("сеньорская позиция", []):
        m = _words_regex(p).search(title)
        if m and not _NOT_SENIOR.search(title[max(0, m.start() - 25):m.start()]):
            return p
    return ""


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
    if is_service_ad(item, kw):
        return Verdict(False, "реклама сервиса")
    adult = adult_content(item, kw)
    if adult:
        return Verdict(False, f"18+: {adult}")
    if greeting_without_role(item, kw):
        return Verdict(False, "приветствие вместо вакансии")
    instagram = instagram_problem(item, kw)
    if instagram:
        return Verdict(False, f"инстаграм: {instagram}")
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
    not_texts = not_about_texts(item, kw)
    if not_texts:
        return Verdict(False, f"не про тексты: «{not_texts}» в заголовке")
    topic = find_any(title, kw.get("тема в заголовке", [])) or find_any(text, kw.get("тема в тексте", []))
    if not topic:
        return Verdict(False, "не тема: нет слов про тексты")
    if editor_only(item, kw):
        return Verdict(False, "редактор, не копирайтер")
    senior = senior_title(item, kw)
    if senior:
        return Verdict(False, f"старшая позиция: {senior}")
    if is_smm(item):
        shooting = find_any(text, kw.get("smm: съёмки и выезды", []))
        if shooting:
            return Verdict(False, f"smm со съёмками: {shooting}")
    hard_office = find_any(full, kw.get("не удалёнка", []))
    if hard_office:
        return Verdict(False, f"не удалёнка: {hard_office}")
    in_person = onsite(full, kw)
    if in_person:
        return Verdict(False, f"очно: {in_person}")
    remote = find_any(full, kw.get("удалёнка", []))
    city = city_only(item)
    if city and not remote:
        return Verdict(False, f"очно: жить в городе ({city})")
    if not remote:
        office = find_any(full, kw.get("офис", []))
        if office:
            return Verdict(False, f"офис: {office}")
        schedule = hard_schedule(full)
        if schedule:
            return Verdict(False, f"офис по графику: {schedule}")
        if item.channel not in config.TEXT_CHANNELS:
            return Verdict(False, "удалёнка не указана")
    years = experience_years(item)
    if years is not None and years >= config.MAX_EXPERIENCE_YEARS:
        return Verdict(False, f"опыт от {years:g} лет")
    contacts = contacts_of(item)
    if not contacts and item.channel not in config.BUTTON_CONTACT_CHANNELS:
        return Verdict(False, "нет контакта для отклика")
    return Verdict(True, f"тема «{topic}», " + (f"удалёнка «{remote}»" if remote else "формат не указан (текстовый канал)"))


def check(item):
    if config.SELECTOR == "keywords":
        return check_keywords(item)
    raise ValueError(f"Неизвестный способ отбора: {config.SELECTOR}")
