import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot import handlers


def make_update(*, text: str = "hello"):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=456, username="new-user", full_name="New User"),
        message=SimpleNamespace(text=text),
    )


class OpenAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_users_are_created_without_an_access_password(self):
        user = MagicMock()
        session = AsyncMock()
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(handlers, "AsyncSessionLocal", return_value=session_context),
            patch.object(handlers, "_get_or_create_user", new=AsyncMock(return_value=user)),
        ):
            result = await handlers._get_or_create_current_user(make_update())

        self.assertIs(result, user)
        session.commit.assert_awaited_once()

    async def test_text_is_processed_without_an_access_gate(self):
        user = SimpleNamespace(id="user-id", onboarding_state={"completed": True})
        update = make_update()
        context = SimpleNamespace(bot=AsyncMock())
        status = SimpleNamespace(message_id=99)

        session = AsyncMock()
        session.get.return_value = user
        session_context = MagicMock()
        session_context.__aenter__ = AsyncMock(return_value=session)
        session_context.__aexit__ = AsyncMock(return_value=None)

        with (
            patch.object(handlers, "_get_or_create_current_user", new=AsyncMock(return_value=user)),
            patch.object(handlers, "AsyncSessionLocal", return_value=session_context),
            patch.object(handlers, "get_or_create_thread_id", new=AsyncMock(return_value="thread-id")),
            patch.object(handlers.telegram_service, "send_status", new=AsyncMock(return_value=status)),
            patch.object(handlers.telegram_service, "send_message", new=AsyncMock()) as send_message,
            patch.object(handlers, "run_chat_turn", new=AsyncMock(return_value="Reply")),
            patch.object(handlers.memory_service, "get_user_context", new=AsyncMock(return_value="context")),
            patch.object(handlers.memory_service, "log_message", new=AsyncMock()),
            patch.object(handlers, "delete_status", new=AsyncMock()),
        ):
            await handlers.text_message_handler.__wrapped__(update, context)

        send_message.assert_awaited_once_with(123, "Reply")
