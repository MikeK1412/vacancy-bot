"""Тесты фильтров и оформления по косякам рассылок 18–21 октября. Тексты придуманные, сеть не нужна.

    python -m unittest test_filters -v
"""
import unittest
from datetime import datetime, timezone

import selector
from collector import Post
from formatter import _contact_line, _labels, format_vacancy
from textutils import NBSP, pay_of

REMOTE = ["удален", "удалён", "remote"]
_n = 0


def make(text, channel="work_copywriters", part=0):
    """Пост из текстового канала (там слово «удалёнка» не обязательно, контакт нужен)."""
    global _n
    _n += 1
    return Post(channel, 1000 + _n, datetime(2026, 10, 21, tzinfo=timezone.utc), text.strip(), part=part)


def verdict(text, **kw):
    return selector.check(make(text, **kw))


AD = """НейроПеро — AI-копирайтер на базе Claude
Бот в Telegram + сайт, без VPN. Claude Sonnet и Opus, готовые режимы: посты, статьи, лендинги.
Подписка от месяца, первые запросы бесплатно.
@neuropero_bot"""

GOOD_AI = """Сценарист — AI-продакшн
Ищем сценариста для вертикальных мини-сериалов для рилс. Знание нейросетей, работа в Claude и ChatGPT приветствуется.
Задачи: писать сценарии серий, править их вместе с редактором.
Условия: удалёнка, оплата 2 000 ₽ за сценарий.
Писать: @aiprod_hr"""

GREETING = """Доброго октябрьского воскресенья, дорогие
Сегодня делимся мыслями о том, как проходит осень и что читать в выходные.
Хороших вам выходных!
Удалёнка. @weekend_channel"""

GREETING_WITH_ROLE = """Доброго октябрьского воскресенья, дорогие
Ищем копирайтера в команду онлайн-школы, удалённо, 50 000 ₽ в месяц.
Писать: @school_hr"""

ADULT = """Копирайтер для канала «Грань Hard»
Тематика 18+, жёсткая тематика, тексты для взрослой аудитории.
Удалённо, оплата 30 000 ₽ в месяц.
@hard_hr"""

AGE_ONLY = """Копирайтер в интернет-магазин
Требования: возраст 18+, грамотность. Удалённо, 30 000 ₽ в месяц.
@shop_hr"""

SMM = """SMM-менеджер в студию
Ведение соцсетей, контент-план. Удалённо, 40 000 ₽ в месяц.
@studio_hr"""

SMM_WRITER = """SMM-копирайтер в студию
Тексты для соцсетей. Удалённо, 40 000 ₽ в месяц.
@studio_hr"""

CRM = """CRM-маркетолог
Настройка рассылок и цепочек писем. Удалённо, 60 000 ₽ в месяц.
@crm_hr"""


class ServiceAds(unittest.TestCase):
    def test_ad_rejected(self):
        v = verdict(AD)
        self.assertFalse(v.ok)
        self.assertEqual(v.reason, "реклама сервиса")

    def test_ad_with_seek_word_about_product_rejected(self):
        text = ("Одна выдуманная цифра может стоить заказчика.\n\n"
                "НейроПеро https://app.example.ru/?utm_source=tg&utm_medium=rk ищет свежие данные в интернете и показывает, "
                "откуда взята каждая цифра.\n\nНейроПеро – рабочее место копирайтера. 10 000 знаков текста – бесплатно.")
        v = verdict(text)
        self.assertFalse(v.ok)
        self.assertEqual(v.reason, "реклама сервиса")

    def test_vacancy_with_ai_skills_passes(self):
        self.assertTrue(verdict(GOOD_AI).ok, verdict(GOOD_AI).reason)

    def test_vacancy_with_models_and_no_hiring_words_still_one_signal(self):
        text = """Копирайтер нейротекстов
Задачи: править тексты, написанные в Claude и GPT. Удалённо, 50 000 ₽ в месяц.
@ai_edit_hr"""
        self.assertTrue(verdict(text).ok, verdict(text).reason)


class GreetingTitle(unittest.TestCase):
    def test_greeting_without_role_rejected(self):
        v = verdict(GREETING)
        self.assertFalse(v.ok)
        self.assertEqual(v.reason, "приветствие вместо вакансии")

    def test_greeting_with_role_in_seek_phrase_passes(self):
        self.assertTrue(verdict(GREETING_WITH_ROLE).ok, verdict(GREETING_WITH_ROLE).reason)


    def test_short_digest_title_is_not_greeting(self):
        text = "20. PR\nИщем PR-менеджера, удалённо, 50 000 ₽ в месяц. @pr_hr"
        self.assertNotEqual(verdict(text, part=20).reason, "приветствие вместо вакансии")


class AudienceBonus(unittest.TestCase):
    def pay(self, text):
        return pay_of(make("Сценарист\n" + text))

    def test_views_bonus_is_not_pay(self):
        self.assertEqual(self.pay("оплата сдельная за ролики + бонусы за 500тыс. и 1млн просмотров"), "")

    def test_subscribers_reach_likes_not_pay(self):
        self.assertEqual(self.pay("бонус за 10 тыс. подписчиков"), "")
        self.assertEqual(self.pay("бонус при охвате от 100 тыс."), "")
        self.assertEqual(self.pay("премия за 5к лайков"), "")

    def test_normal_pay_unchanged(self):
        self.assertEqual(self.pay("Оплата: 150 000 ₽/мес"), f"150{NBSP}000{NBSP}₽/мес")
        self.assertEqual(self.pay("Оплата 80 000–110 000 ₽"), f"80{NBSP}000–110{NBSP}000{NBSP}₽")
        self.assertEqual(self.pay("от 10 000 ₽ за проект"), f"от 10{NBSP}000{NBSP}₽ за проект")

    def test_pay_survives_audience_words_in_other_clause(self):
        self.assertEqual(self.pay("от 10 000 ₽ за проект, аудитория 5000 подписчиков"), f"от 10{NBSP}000{NBSP}₽ за проект")


class Adult(unittest.TestCase):
    def test_adult_rejected(self):
        v = verdict(ADULT)
        self.assertFalse(v.ok)
        self.assertTrue(v.reason.startswith("18+"), v.reason)

    def test_candidate_age_is_fine(self):
        self.assertTrue(verdict(AGE_ONLY).ok, verdict(AGE_ONLY).reason)

    def test_age_requirement_in_list_is_fine(self):
        for req in ("✓ Гражданство РФ, 18+", "• 18+", "18+, грамотная речь"):
            text = f"Копирайтер\nТребования:\n{req}\nУдалённо, 30 000 ₽ в месяц. @a_hr"
            self.assertTrue(verdict(text).ok, req)

    def test_hard_topic_phrase(self):
        text = "Автор постов\nТг-канал ищет автора, включая жесткую тематику 18+. Удалённо, 30 000 ₽ в месяц. @a_hr"
        self.assertFalse(verdict(text).ok)

    def test_other_markers(self):
        for word in ("эротика", "интим-товары", "контент для взрослых"):
            text = f"Копирайтер\nПишем про {word}. Удалённо, 30 000 ₽ в месяц. @a_hr"
            self.assertFalse(verdict(text).ok, word)


class NotAboutTexts(unittest.TestCase):
    def test_smm_manager_rejected(self):
        v = verdict(SMM)
        self.assertFalse(v.ok)
        self.assertTrue(v.reason.startswith("не про тексты"), v.reason)

    def test_crm_rejected(self):
        self.assertFalse(verdict(CRM).ok)

    def test_smm_copywriter_passes(self):
        self.assertTrue(verdict(SMM_WRITER).ok, verdict(SMM_WRITER).reason)

    def test_rule_can_be_switched_off(self):
        kw = {**selector.keywords(), "не про тексты: заголовок": []}
        original = selector._keywords
        selector._keywords = kw
        try:
            self.assertNotEqual(verdict(SMM).reason.split(":")[0], "не про тексты")
        finally:
            selector._keywords = original


class Formatting(unittest.TestCase):
    def test_no_digest_label(self):
        item = make("1. #Копирайтер\nУдалённо, 30 000 ₽ в месяц\n@digest_hr", part=1)
        self.assertNotIn("из подборки", _contact_line(item))
        self.assertEqual(_contact_line(item), "✉️ @digest_hr")

    def test_no_contact_phrase(self):
        item = make("Копирайтер\nУдалённо, 30 000 ₽ в месяц", channel="textodromo")
        self.assertEqual(_contact_line(item), "✉️ Контакт — в оригинальном посте (ссылка в заголовке)")

    def test_project_label_not_duplicated(self):
        item = make("Сценарист\nУдалённо, проектная работа, 2 000 ₽ за проект. @a_hr")
        labels = _labels(item, REMOTE).split(" · ")
        self.assertEqual(labels.count("проект"), 0)
        self.assertEqual(labels[0], f"💰 2{NBSP}000{NBSP}₽ за проект")
        self.assertIn("удалёнка", labels)

    def test_project_label_kept_without_pay(self):
        item = make("Сценарист\nУдалённо, проектная работа. @a_hr")
        self.assertEqual(_labels(item, REMOTE), "удалёнка · проект")

    def test_labels_in_one_line(self):
        item = make("Сценарист\nУдалённо, частичная занятость, проектная работа, 2 000 ₽ в месяц. @a_hr")
        out = format_vacancy(1, item, REMOTE)
        label_lines = [l for l in out.split("\n") if "удалёнка" in l]
        self.assertEqual(len(label_lines), 1)
        self.assertIn("частичная", label_lines[0])
        self.assertEqual(label_lines[0].count("проект"), 1)


class NormalVacanciesPass(unittest.TestCase):
    def test_scenarist_ai_production(self):
        self.assertTrue(verdict(GOOD_AI).ok)

    def test_content_editor_mantera(self):
        text = """Контент-редактор — Mantera Group
Ищем контент-редактора: писать тексты для сайта и рассылок, вычитывать материалы коллег.
Условия: 150 000 ₽/мес, удалёнка, опыт от 2 лет.
Писать: @mantera_hr"""
        v = verdict(text)
        self.assertTrue(v.ok, v.reason)
        self.assertEqual(pay_of(make(text)), f"150{NBSP}000{NBSP}₽/мес")

    def test_news_editor_abzac(self):
        text = """Редактор новостей — Мы Абзац Медиа
Ищем редактора новостей: писать тексты новостей, проверять факты, работать с лентой.
Условия: до 100 000 ₽/мес, удалёнка.
Писать: @abzac_hr"""
        v = verdict(text)
        self.assertTrue(v.ok, v.reason)
        self.assertEqual(pay_of(make(text)), f"до 100{NBSP}000{NBSP}₽/мес")

    def test_content_marketer_gofar(self):
        text = """Контент-маркетолог — GOFAR
Ищем контент-маркетолога: писать статьи и рассылки, вести контент-план.
Условия: удалёнка, оплата 70 000 ₽ в месяц.
Писать: @gofar_hr"""
        v = verdict(text)
        self.assertTrue(v.ok, v.reason)


if __name__ == "__main__":
    unittest.main()
