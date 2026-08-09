import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from app.agents.chat.graph import run_chat_turn
from app.agents.onboarding.graph import run_onboarding
from app.database import AsyncSessionLocal
from app.decorators.error_handler import handle_errors
from app.models.user import User
from app.services import memory_service, rag_service, telegram_service
from app.services.telegram_service import delete_status
logger = logging.getLogger("finassist.bot")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


async def _get_or_create_user(db, update: Update) -> User:
    tg_user = update.effective_user
    result = await db.execute(select(User).where(User.telegram_id == tg_user.id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=tg_user.id, telegram_username=tg_user.username, display_name=tg_user.full_name)
        db.add(user)
        await db.flush()
    return user


def _onboarding_complete(user: User) -> bool:
    return bool((user.onboarding_state or {}).get("completed"))


@handle_errors()
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with AsyncSessionLocal() as db:
        user = await _get_or_create_user(db, update)
        reply, _ = await run_onboarding(db, user, incoming_text="")
        await db.commit()
    await telegram_service.send_message(update.effective_chat.id, reply)


@handle_errors()
async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    chat_id = update.effective_chat.id

    status_message = await telegram_service.send_status(
    chat_id,
    "🔎 Working on your request..."
)

    status_message_id = status_message.message_id

    try:
        async with AsyncSessionLocal() as db:
            user = await _get_or_create_user(db, update)

            if not _onboarding_complete(user):
                reply, _ = await run_onboarding(db, user, incoming_text=text)
                await db.commit()
                await telegram_service.send_message(update.effective_chat.id, reply)
                return

            await memory_service.log_message(db, user.id, str(user.telegram_id), "user", text)
            user_context = await memory_service.get_user_context(db, user.id)
            await db.commit()

        reply = await run_chat_turn(
            user_id=str(user.id),
            thread_id=str(user.telegram_id),
            user_context=user_context,
            user_text=text,
            chat_id=chat_id,
            status_message_id=status_message_id,
        )

        async with AsyncSessionLocal() as db:
            await memory_service.log_message(db, user.id, str(user.telegram_id), "assistant", reply)
            await db.commit()

        await telegram_service.send_message(update.effective_chat.id, reply)
    finally:
        await delete_status(chat_id, status_message_id)


@handle_errors()
async def document_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    doc = update.message.document
    filename = doc.file_name or "uploaded document"
    if doc.file_size and doc.file_size > MAX_UPLOAD_BYTES:
        await telegram_service.send_message(
            update.effective_chat.id,
            "That file is too large to process. Please upload a file smaller than 20 MB.",
        )
        return

    file = await context.bot.get_file(doc.file_id)
    file_bytes = bytes(await file.download_as_bytearray())

    if filename.lower().endswith(".pdf"):
        text = await rag_service.extract_pdf_text(file_bytes)
        source_type = "pdf"
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
        source_type = "document"

    if not text.strip():
        await telegram_service.send_message(
            update.effective_chat.id,
            "I couldn't extract readable text from that file. Try a text-based PDF or document.",
        )
        return

    async with AsyncSessionLocal() as db:
        user = await _get_or_create_user(db, update)

        # Save the uploaded file as a user message
        await memory_service.log_message(
            db,
            user.id,
            str(user.telegram_id),
            "user",
            f"[File uploaded] {filename}",
        )

        # Extracted text is split into chunks and indexed for RAG
        n_chunks = await rag_service.ingest_document(
            db,
            user.id,
            text,
            source_type,
            filename=filename,
        )

        reply = (
            f"Read through {filename} "
            f"({n_chunks} sections indexed). "
            "Ask me anything about it."
        )

        # Save the bot's response as an assistant message
        await memory_service.log_message(
            db,
            user.id,
            str(user.telegram_id),
            "assistant",
            reply,
        )

        await db.commit()

    await telegram_service.send_message(
        update.effective_chat.id,
        reply,
    )

@handle_errors()
async def photo_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    photo = update.message.photo[-1]

    file = await context.bot.get_file(photo.file_id)
    file_bytes = bytes(await file.download_as_bytearray())

    extracted = await rag_service.extract_image_text(file_bytes)
    if not extracted or not extracted.strip():
        await telegram_service.send_message(
            update.effective_chat.id,
            "I couldn't read any text or data from that image. Please try a clearer image.",
        )
        return

    async with AsyncSessionLocal() as db:
        user = await _get_or_create_user(db, update)

        # Save the image upload as a user message
        await memory_service.log_message(
            db,
            user.id,
            str(user.telegram_id),
            "user",
            "[Image uploaded]",
            message_type="image",
        )

        # Index the extracted image content for RAG
        await rag_service.ingest_document(
            db,
            user.id,
            extracted,
            source_type="image",
            filename="photo",
        )

        reply = extracted

        # Save the bot's response
        await memory_service.log_message(
            db,
            user.id,
            str(user.telegram_id),
            "assistant",
            reply,
        )

        await db.commit()

    await telegram_service.send_message(
        update.effective_chat.id,
        reply,
    )


@handle_errors()
async def voice_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    voice = update.message.voice

    file = await context.bot.get_file(voice.file_id)
    file_bytes = bytes(await file.download_as_bytearray())

    transcript = await rag_service.transcribe_voice(file_bytes)
    if not transcript or not transcript.strip():
        await telegram_service.send_message(
            update.effective_chat.id,
            "I couldn't transcribe that voice message. Please try sending it again.",
        )
        return

    async with AsyncSessionLocal() as db:
        user = await _get_or_create_user(db, update)

        # Save the transcribed voice message as the user's message
        await memory_service.log_message(
            db,
            user.id,
            str(user.telegram_id),
            "user",
            transcript,
            message_type="voice",
        )

        user_context = await memory_service.get_user_context(
            db,
            user.id,
        )

        await db.commit()

    chat_id = update.effective_chat.id
    status_message = await telegram_service.send_status(
        chat_id, "🔎 Working on your voice message..."
    )

    try:
        # Let the normal chat agent process the transcription.
        reply = await run_chat_turn(
            user_id=str(user.id),
            thread_id=str(user.telegram_id),
            user_context=user_context,
            user_text=transcript,
            chat_id=chat_id,
            status_message_id=status_message.message_id,
        )

        async with AsyncSessionLocal() as db:
            await memory_service.log_message(
                db,
                user.id,
                str(user.telegram_id),
                "assistant",
                reply,
            )
            await db.commit()

        await telegram_service.send_message(chat_id, reply)
    finally:
        await delete_status(chat_id, status_message.message_id)
