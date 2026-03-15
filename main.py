import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters
)
from handlers.command_handlers import start, help_command, reset, status
from handlers.message_handlers import handle_message
from handlers.file_handlers import handle_document
from database.db import init_db
from config import TELEGRAM_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    init_db()
    logger.info("База данных инициализирована")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен и слушает сообщения...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
