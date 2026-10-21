"""Тесты рассылки в несколько чатов. Значения придуманные, в Telegram ничего не уходит.

    python -m unittest test_chat_ids -v
"""
import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

import requests

import config
import tg
from main import deliver

A, B = "-1001111111111", "-1002222222222"
TOKEN = "123456:FAKE-TOKEN"


class ParseChatIds(unittest.TestCase):
    def test_one_id(self):
        self.assertEqual(config.parse_chat_ids(A), ([A], []))

    def test_two_ids(self):
        self.assertEqual(config.parse_chat_ids(f"{A},{B}"), ([A, B], []))

    def test_two_ids_with_space(self):
        self.assertEqual(config.parse_chat_ids(f"{A}, {B}"), ([A, B], []))
        self.assertEqual(config.parse_chat_ids(f" {A} ,  {B} "), ([A, B], []))

    def test_trailing_empty(self):
        self.assertEqual(config.parse_chat_ids(f"{A},{B},"), ([A, B], []))
        self.assertEqual(config.parse_chat_ids(f"{A},,{B}, "), ([A, B], []))

    def test_garbage(self):
        self.assertEqual(config.parse_chat_ids(f"{A},abc,12 34,{B}"), ([A, B], ["abc", "12 34"]))
        self.assertEqual(config.parse_chat_ids("мусор;;;"), ([], ["мусор;;;"]))

    def test_empty(self):
        self.assertEqual(config.parse_chat_ids(""), ([], []))
        self.assertEqual(config.parse_chat_ids(None), ([], []))
        self.assertEqual(config.parse_chat_ids(" , ,"), ([], []))

    def test_duplicates_collapse(self):
        self.assertEqual(config.parse_chat_ids(f"{A},{A}"), ([A], []))

    def test_channel_username(self):
        self.assertEqual(config.parse_chat_ids("@my_channel"), (["@my_channel"], []))


class Deliver(unittest.TestCase):
    def run_deliver(self, ids, fail=()):
        calls = []

        def fake_send(token, chat_id, text):
            calls.append(chat_id)
            if chat_id in fail:
                raise tg.TelegramError("sendMessage: Forbidden: bot was kicked")

        out = io.StringIO()
        with redirect_stdout(out):
            result = deliver(TOKEN, ids, "текст", send=fake_send)
        return result, calls, out.getvalue()

    def test_all_ok(self):
        (sent, failed), calls, _ = self.run_deliver([A, B])
        self.assertEqual((sent, failed, calls), ([A, B], [], [A, B]))

    def test_one_fails_others_still_get_message(self):
        (sent, failed), calls, log = self.run_deliver([A, B], fail={A})
        self.assertEqual((sent, failed), ([B], [A]))
        self.assertEqual(calls, [A, B])
        self.assertIn(A, log)
        self.assertNotIn(TOKEN, log)

    def test_all_fail(self):
        (sent, failed), _, _ = self.run_deliver([A, B], fail={A, B})
        self.assertEqual((sent, failed), ([], [A, B]))


class TokenNotLeaked(unittest.TestCase):
    def test_network_error_hides_token(self):
        err = requests.ConnectionError(f"HTTPSConnectionPool: url /bot{TOKEN}/sendMessage failed")
        with mock.patch("tg.requests.post", side_effect=err):
            with self.assertRaises(tg.TelegramError) as cm:
                tg.send_message(TOKEN, A, "x")
        self.assertNotIn(TOKEN, str(cm.exception))
        self.assertIsNone(cm.exception.__cause__)
        self.assertTrue(cm.exception.__suppress_context__)


if __name__ == "__main__":
    unittest.main()
