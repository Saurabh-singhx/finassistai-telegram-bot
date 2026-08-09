import unittest
from unittest.mock import AsyncMock, patch

from app.services import telegram_service


class TelegramDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_untrusted_text_without_markdown_parsing(self):
        bot = AsyncMock()
        text = "A malformed [link and an unmatched * marker"

        with patch.object(telegram_service, "get_bot", return_value=bot):
            await telegram_service.send_message(42, text)

        bot.send_message.assert_awaited_once_with(chat_id=42, text=text)

    def test_splits_long_text_at_a_word_boundary(self):
        text = "word " * 1_000

        chunks = telegram_service._split_message(text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= telegram_service.TELEGRAM_MAX_LEN for chunk in chunks))
        self.assertEqual(" ".join(chunks).split(), text.split())
