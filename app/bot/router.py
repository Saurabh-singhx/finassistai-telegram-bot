from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.bot import handlers


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handlers.document_handler))
    application.add_handler(MessageHandler(filters.PHOTO, handlers.photo_handler))
    application.add_handler(MessageHandler(filters.VOICE, handlers.voice_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text_message_handler))
