"""Настройки парсера. Токены здесь не храним, они берутся из .env или переменных окружения."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Публичные каналы (юзернейм без @). Читаются через t.me/s/<юзернейм>.
# Разбор каналов и почему выбраны именно эти: каналы.md
CHANNELS = [
    "rueventjob",            # Удаленка - вся творческая работа
    "textodromo",            # Текстодром
    "work_editor",           # Работа с текстами — вакансии
    "work_copywriters",      # Работа для копирайтеров и редакторов
    "freelancechoice",       # Freelance Choice
    "uvetrovoi",             # ФРИЛАНС
    "copywriter_vacancies",  # Вакансии для копирайтеров
    "seohr",                 # SEO HR
    "zdemcv",                # Ждём резюме | Лайфхакер
    "normrabota",            # Норм работа
    "freegolup",             # Голубь на Фрилансе
    "self_ma",               # Копирайтер, редактор — удаленная работа
    "Work4writers",          # Work for writers
]

# Каналы целиком про тексты: в них не требуем слова «удалёнка», отсекаем только явный офис или гибрид.
TEXT_CHANNELS = {"textodromo", "work_editor", "work_copywriters", "copywriter_vacancies", "Work4writers"}

DAYS_BACK = 3              # за сколько дней собирать посты
MAX_VACANCIES = 5          # сколько вакансий отправлять за раз (не больше)
MAX_PER_CHANNEL = 2        # не больше стольких вакансий из одного канала в сообщении
PAID_PRIORITY_DAYS = 2     # вакансии с оплатой за эти дни идут первыми, потом остальные по свежести
SENT_KEEP_DAYS = 30        # сколько дней помнить отправленные вакансии
DUPLICATE_THRESHOLD = 0.6  # похожесть текстов (0..1), выше которой две вакансии считаются одной
TIMEZONE_OFFSET_HOURS = 3  # Москва, для сравнения «свежести» по дням

# Чем отбирать вакансии: "keywords" (списки слов из keywords.txt).
# Позже сюда добавится вариант с нейросетью, см. selector.py
SELECTOR = "keywords"

KEYWORDS_FILE = BASE_DIR / "keywords.txt"
SENT_FILE = BASE_DIR / "sent.json"
ENV_FILE = BASE_DIR / ".env"


def load_env(path=ENV_FILE):
    """Читает KEY=VALUE из .env в переменные окружения (уже заданные не трогает)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def telegram_settings():
    load_env()
    token = os.environ.get("BOT_TOKEN", "").strip()
    chat_id = os.environ.get("CHAT_ID", "").strip()
    return token, chat_id
