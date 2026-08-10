import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app import main
from app.bot import handlers


def make_update(*, text: str = "hello"):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=456, username="new-user", full_name="New User"),
        message=SimpleNamespace(
            text=text,
            document=SimpleNamespace(file_name="report.pdf", file_size=10, file_id="doc-id"),
            photo=[SimpleNamespace(file_id="photo-id")],
            voice=SimpleNamespace(file_id="voice-id"),
        ),
    )


class AccessVerificationTests(unittest.IsolatedAsyncioTestCase):
    def test_startup_requires_the_access_password(self):
        with patch.object(main.settings, "ONE_TIME_PASSWORD", None):
            with self.assertRaisesRegex(RuntimeError, "ONE_TIME_PASSWORD"):
                main._validate_access_settings()

        with patch.object(main.settings, "ONE_TIME_PASSWORD", "configured"):
            main._validate_access_settings()

    def test_password_comparison_requires_an_exact_configured_value(self):
        with patch.object(handlers.settings, "ONE_TIME_PASSWORD", "private-access"):
            self.assertTrue(handlers._password_matches("private-access"))
            self.assertFalse(handlers._password_matches("private-access "))
            self.assertFalse(handlers._password_matches("wrong"))

        with patch.object(handlers.settings, "ONE_TIME_PASSWORD", None):
            self.assertFalse(handlers._password_matches("anything"))

    async def test_correct_password_is_persisted_for_future_messages(self):
        user = SimpleNamespace(is_verified=False)
        session = AsyncMock()
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(handlers, "AsyncSessionLocal", return_value=session_context),
            patch.object(handlers, "_get_or_create_user", new=AsyncMock(return_value=user)),
            patch.object(handlers.settings, "ONE_TIME_PASSWORD", "private-access"),
        ):
            result = await handlers._authorize_user(make_update(), password="private-access")

        self.assertEqual(result, (user, True, True))
        self.assertTrue(user.is_verified)
        session.commit.assert_awaited_once()

    async def test_unverified_text_never_starts_status_or_chat(self):
        update = make_update(text="wrong-password")
        context = SimpleNamespace(bot=AsyncMock())

        with (
            patch.object(handlers, "_authorize_user", new=AsyncMock(return_value=(MagicMock(), False, False))),
            patch.object(handlers.telegram_service, "send_message", new=AsyncMock()) as send_message,
            patch.object(handlers.telegram_service, "send_status", new=AsyncMock()) as send_status,
            patch.object(handlers, "run_chat_turn", new=AsyncMock()) as run_chat,
        ):
            await handlers.text_message_handler.__wrapped__(update, context)

        send_message.assert_awaited_once_with(123, handlers.ACCESS_DENIED_PROMPT)
        send_status.assert_not_awaited()
        run_chat.assert_not_awaited()

    async def test_unverified_media_never_downloads_or_calls_ai(self):
        context = SimpleNamespace(bot=AsyncMock())
        blocked_user = (MagicMock(), False, False)

        with (
            patch.object(handlers, "_authorize_user", new=AsyncMock(return_value=blocked_user)),
            patch.object(handlers.telegram_service, "send_message", new=AsyncMock()) as send_message,
            patch.object(handlers.rag_service, "extract_pdf_text", new=AsyncMock()) as extract_pdf,
            patch.object(handlers.rag_service, "extract_image_text", new=AsyncMock()) as extract_image,
            patch.object(handlers.rag_service, "transcribe_voice", new=AsyncMock()) as transcribe_voice,
        ):
            await handlers.document_handler.__wrapped__(make_update(), context)
            await handlers.photo_handler.__wrapped__(make_update(), context)
            await handlers.voice_handler.__wrapped__(make_update(), context)

        self.assertEqual(send_message.await_count, 3)
        context.bot.get_file.assert_not_awaited()
        extract_pdf.assert_not_awaited()
        extract_image.assert_not_awaited()
        transcribe_voice.assert_not_awaited()

    async def test_verified_password_starts_onboarding_not_chat(self):
        user = SimpleNamespace(id="user-id")
        update = make_update(text="private-access")
        context = SimpleNamespace(bot=AsyncMock())

        session = AsyncMock()
        session.get.return_value = user
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(handlers, "_authorize_user", new=AsyncMock(return_value=(user, True, True))),
            patch.object(handlers, "AsyncSessionLocal", return_value=session_context),
            patch.object(handlers, "run_onboarding", new=AsyncMock(return_value=("Welcome", False))) as onboarding,
            patch.object(handlers, "run_chat_turn", new=AsyncMock()) as run_chat,
            patch.object(handlers.telegram_service, "send_message", new=AsyncMock()) as send_message,
        ):
            await handlers.text_message_handler.__wrapped__(update, context)

        onboarding.assert_awaited_once_with(session, user, incoming_text="")
        run_chat.assert_not_awaited()
        send_message.assert_awaited_once_with(123, "Access verified.\n\nWelcome")
