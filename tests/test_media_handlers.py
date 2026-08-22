import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.bot import handlers


def make_update_for_doc(*, file_name="test.pdf", file_size=1024):
    doc = SimpleNamespace(file_id="doc_123", file_name=file_name, file_size=file_size)
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=456, username="test-user", full_name="Test User"),
        message=SimpleNamespace(document=doc),
    )


def make_update_for_photo():
    photo = SimpleNamespace(file_id="photo_123")
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=456, username="test-user", full_name="Test User"),
        message=SimpleNamespace(photo=[photo]),
    )


def make_update_for_voice():
    voice = SimpleNamespace(file_id="voice_123")
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=456, username="test-user", full_name="Test User"),
        message=SimpleNamespace(voice=voice),
    )


class MediaHandlersTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=uuid.uuid4(), onboarding_state={"completed": True})
        self.session = AsyncMock()
        self.session.get.return_value = self.user
        self.session_context = MagicMock()
        self.session_context.__aenter__ = AsyncMock(return_value=self.session)
        self.session_context.__aexit__ = AsyncMock(return_value=None)
        self.status = SimpleNamespace(message_id=88)

    async def test_document_handler_success(self):
        update = make_update_for_doc(file_name="report.pdf")
        tg_file = AsyncMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"pdfcontent"))
        context = SimpleNamespace(bot=AsyncMock(get_file=AsyncMock(return_value=tg_file)))

        with (
            patch.object(handlers, "_get_or_create_current_user", new=AsyncMock(return_value=self.user)),
            patch.object(handlers, "AsyncSessionLocal", return_value=self.session_context),
            patch.object(handlers, "get_or_create_thread_id", new=AsyncMock(return_value="thread-doc")) as mock_thread,
            patch.object(handlers.rag_service, "extract_pdf_text", new=AsyncMock(return_value="Extracted PDF text")),
            patch.object(handlers.rag_service, "ingest_document", new=AsyncMock(return_value=3)),
            patch.object(handlers.memory_service, "log_message", new=AsyncMock()) as mock_log,
            patch.object(handlers.telegram_service, "send_status", new=AsyncMock(return_value=self.status)),
            patch.object(handlers.telegram_service, "send_message", new=AsyncMock()) as mock_send,
            patch.object(handlers, "delete_status", new=AsyncMock()) as mock_del_status,
        ):
            await handlers.document_handler.__wrapped__(update, context)

            mock_thread.assert_awaited_once_with(self.session, self.user.id)
            self.assertEqual(mock_log.await_count, 2)
            self.session.commit.assert_awaited_once()
            mock_send.assert_awaited_once()
            mock_del_status.assert_awaited_once_with(123, 88)
            sent_text = mock_send.call_args[0][1]
            self.assertIn("Read through report.pdf", sent_text)

    async def test_photo_handler_success(self):
        update = make_update_for_photo()
        tg_file = AsyncMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"imagebytes"))
        context = SimpleNamespace(bot=AsyncMock(get_file=AsyncMock(return_value=tg_file)))

        with (
            patch.object(handlers, "_get_or_create_current_user", new=AsyncMock(return_value=self.user)),
            patch.object(handlers, "AsyncSessionLocal", return_value=self.session_context),
            patch.object(handlers, "get_or_create_thread_id", new=AsyncMock(return_value="thread-photo")) as mock_thread,
            patch.object(handlers.rag_service, "extract_image_text", new=AsyncMock(return_value="Receipt total: $42.00")),
            patch.object(handlers.rag_service, "ingest_document", new=AsyncMock(return_value=1)),
            patch.object(handlers.memory_service, "log_message", new=AsyncMock()) as mock_log,
            patch.object(handlers.telegram_service, "send_status", new=AsyncMock(return_value=self.status)),
            patch.object(handlers.telegram_service, "send_message", new=AsyncMock()) as mock_send,
            patch.object(handlers, "delete_status", new=AsyncMock()) as mock_del_status,
        ):
            await handlers.photo_handler.__wrapped__(update, context)

            mock_thread.assert_awaited_once_with(self.session, self.user.id)
            self.assertEqual(mock_log.await_count, 2)
            self.session.commit.assert_awaited_once()
            mock_del_status.assert_awaited_once_with(123, 88)
            mock_send.assert_awaited_once_with(123, "Receipt total: $42.00")

    async def test_voice_handler_success(self):
        update = make_update_for_voice()
        tg_file = AsyncMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"voicebytes"))
        context = SimpleNamespace(bot=AsyncMock(get_file=AsyncMock(return_value=tg_file)))

        with (
            patch.object(handlers, "_get_or_create_current_user", new=AsyncMock(return_value=self.user)),
            patch.object(handlers, "AsyncSessionLocal", return_value=self.session_context),
            patch.object(handlers, "get_or_create_thread_id", new=AsyncMock(return_value="thread-voice")) as mock_thread,
            patch.object(handlers.rag_service, "transcribe_voice", new=AsyncMock(return_value="What is the price of AAPL?")),
            patch.object(handlers.memory_service, "get_user_context", new=AsyncMock(return_value="ctx")),
            patch.object(handlers.telegram_service, "send_status", new=AsyncMock(return_value=self.status)),
            patch.object(handlers, "run_chat_turn", new=AsyncMock(return_value="AAPL is $180")),
            patch.object(handlers.memory_service, "log_message", new=AsyncMock()) as mock_log,
            patch.object(handlers.telegram_service, "send_message", new=AsyncMock()) as mock_send,
            patch.object(handlers, "delete_status", new=AsyncMock()) as mock_del_status,
        ):
            await handlers.voice_handler.__wrapped__(update, context)

            mock_thread.assert_awaited_once_with(self.session, self.user.id)
            self.assertEqual(mock_log.await_count, 2)
            self.assertEqual(self.session.commit.await_count, 2)
            mock_send.assert_awaited_once_with(123, "AAPL is $180")
            mock_del_status.assert_awaited_once_with(123, 88)
