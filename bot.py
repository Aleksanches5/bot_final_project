"""
Telegram-бот для анализа рекламных кампаний с GigaChat.

Запуск:
    python bot.py

Переменные окружения (.env):
    TELEGRAM_TOKEN    — токен бота от @BotFather
    GIGACHAT_CREDS    — Base64-ключ от GigaChat (из кабинета Сбера)
    GIGACHAT_MODEL    — модель (по умолчанию GigaChat-Pro)
    DB_PATH           — путь к SQLite базе (по умолчанию bot_memory.db)
"""

import os
import io
import logging
import asyncio
import warnings

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from memory import (
    init_db, add_message, get_history, clear_history,
    save_knowledge, get_knowledge, delete_knowledge,
    save_ad_data, get_ad_data, delete_ad_data, get_ad_data_summary,
)
from gigachat_client import GigaChatClient
from data_parser import (
    parse_csv_bytes, parse_excel_bytes, parse_csv_text,
    summarize_data, detect_channel_from_columns, extract_metrics_from_text,
)
from prompts import SYSTEM_PROMPT, build_context_prompt

# Подавляем InsecureRequestWarning от urllib3 (Сбер использует свой CA)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GIGACHAT_CREDS = os.getenv("GIGACHAT_CREDS")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-Pro")

if not TELEGRAM_TOKEN or not GIGACHAT_CREDS:
    raise RuntimeError("Укажите TELEGRAM_TOKEN и GIGACHAT_CREDS в .env файле!")

gigachat = GigaChatClient(credentials=GIGACHAT_CREDS, model=GIGACHAT_MODEL)

# ─────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────

async def ask_gigachat(user_id: int, user_message: str) -> str:
    """Отправляет запрос в GigaChat с учётом истории и базы знаний."""
    knowledge = get_knowledge(user_id)
    ad_summary = get_ad_data_summary(user_id)
    context = build_context_prompt(knowledge, ad_summary)

    # Строим системный промпт с контекстом
    system = SYSTEM_PROMPT
    if context.strip():
        system = SYSTEM_PROMPT + "\n\n" + context

    history = get_history(user_id, limit=20)
    history.append({"role": "user", "content": user_message})

    # Запускаем в executor чтобы не блокировать event loop
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(
        None,
        lambda: gigachat.chat(
            messages=history,
            system_prompt=system,
            temperature=0.5,
            max_tokens=3000,
        )
    )

    # Сохраняем в историю
    add_message(user_id, "user", user_message)
    add_message(user_id, "assistant", reply)

    return reply


def channel_keyboard():
    """Инлайн-клавиатура выбора рекламного канала."""
    channels = ["Яндекс.Директ", "Google Ads", "VK Реклама", "Meta Ads", "myTarget", "Другое"]
    buttons = [[InlineKeyboardButton(ch, callback_data=f"channel:{ch}")] for ch in channels]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="channel:cancel")])
    return InlineKeyboardMarkup(buttons)


# ─────────────────────────────────────────────────────────────
# Команды
# ─────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Привет! Я бот для анализа и оптимизации рекламных кампаний.*\n\n"
        "Я работаю на базе GigaChat и умею:\n"
        "• Анализировать рекламные данные (CSV, Excel, текст)\n"
        "• Давать приоритизированные рекомендации по оптимизации\n"
        "• Использовать справки с рекламных платформ\n"
        "• Помнить все загруженные данные между сессиями\n\n"
        "📌 *Команды:*\n"
        "/help — подробная справка\n"
        "/upload\\_data — загрузить рекламные данные (или просто отправь файл)\n"
        "/add\\_knowledge — добавить справку по каналу\n"
        "/my\\_data — показать загруженные данные\n"
        "/my\\_knowledge — показать базу знаний\n"
        "/analyze — запустить анализ всех данных\n"
        "/clear\\_history — очистить историю диалога\n"
        "/reset — полный сброс (история + данные + знания)\n\n"
        "💬 Просто напиши вопрос или вставь данные текстом!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Подробная справка*\n\n"
        "*Как загрузить данные:*\n"
        "1. Отправь `.csv` или `.xlsx` файл прямо в чат\n"
        "2. Или отправь данные текстом в формате CSV\n"
        "3. Или опиши метрики словами: «CTR: 2%, показы: 50000»\n\n"
        "*Как добавить справку по каналу:*\n"
        "1. Введи `/add_knowledge` и следуй инструкциям\n"
        "2. Или отправь ссылку на справку: `/add_url https://...`\n\n"
        "*Как получить анализ:*\n"
        "• Загрузи данные → напиши «проанализируй» или «дай рекомендации»\n"
        "• Или введи `/analyze` для полного анализа всех данных\n\n"
        "*Примеры запросов:*\n"
        "— «Почему у меня высокий CPC?»\n"
        "— «Как снизить CPL?»\n"
        "— «Какие кампании отключить?»\n"
        "— «Сравни эффективность кампаний»\n"
        "— «Дай план оптимизации на неделю»\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_add_knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "waiting_knowledge_source"
    await update.message.reply_text(
        "📚 *Добавление справки*\n\n"
        "Введи название источника (например: «Справка Яндекс.Директ по стратегиям ставок»):",
        parse_mode="Markdown"
    )


async def cmd_add_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Загружает справку по URL: /add_url https://..."""
    args = context.args
    if not args:
        await update.message.reply_text("Использование: `/add_url https://example.com`", parse_mode="Markdown")
        return

    url = args[0]
    msg = await update.message.reply_text(f"🔄 Загружаю страницу: {url}")

    try:
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, gigachat.fetch_url_content, url)
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка загрузки: {e}")
        return

    user_id = update.effective_user.id
    save_knowledge(user_id, url, content, channel=None)
    await msg.edit_text(
        f"✅ Справка добавлена!\n"
        f"Источник: {url}\n"
        f"Загружено символов: {len(content)}"
    )


async def cmd_upload_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📤 *Загрузка данных*\n\n"
        "Отправь файл (.csv или .xlsx) прямо в чат.\n"
        "Или вставь данные текстом в формате CSV.\n\n"
        "Данные будут сохранены и использованы при анализе.",
        parse_mode="Markdown"
    )


async def cmd_my_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data_list = get_ad_data(user_id)

    if not data_list:
        await update.message.reply_text("📭 Рекламные данные не загружены.")
        return

    text = "📊 *Загруженные данные:*\n\n"
    buttons = []
    for item in data_list:
        ch = item.get("channel") or "—"
        rows = len(item.get("data", []))
        text += f"• `{item['id']}` | {item['filename']} | {ch} | {rows} строк\n"
        buttons.append([InlineKeyboardButton(
            f"🗑 Удалить {item['filename']}", callback_data=f"del_data:{item['id']}"
        )])

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_my_knowledge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    knowledge = get_knowledge(user_id)

    if not knowledge:
        await update.message.reply_text("📭 База знаний пуста. Добавь справки через /add_knowledge или /add_url")
        return

    text = "📚 *База знаний:*\n\n"
    buttons = []
    for k in knowledge:
        ch = f"[{k['channel']}] " if k.get("channel") else ""
        src_short = k["source"][:50]
        text += f"• {ch}{src_short}\n"
        buttons.append([InlineKeyboardButton(
            f"🗑 Удалить: {src_short}", callback_data=f"del_know:{k['source'][:60]}"
        )])

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ad_data = get_ad_data(user_id)

    if not ad_data:
        await update.message.reply_text(
            "❌ Нет загруженных данных для анализа.\n"
            "Загрузи CSV или Excel файл через /upload_data"
        )
        return

    msg = await update.message.reply_text("🔄 Анализирую данные, подожди...")

    try:
        reply = await ask_gigachat(
            user_id,
            "Проведи полный анализ всех загруженных рекламных данных. "
            "Дай развёрнутые рекомендации по оптимизации с приоритетами."
        )
        await msg.edit_text(reply[:4096])
        if len(reply) > 4096:
            # Разбиваем длинный ответ на части
            for chunk_start in range(4096, len(reply), 4096):
                await update.message.reply_text(reply[chunk_start:chunk_start + 4096])
    except Exception as e:
        logger.error(f"GigaChat error: {e}")
        await msg.edit_text(f"❌ Ошибка при обращении к GigaChat: {e}")


async def cmd_clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_history(update.effective_user.id)
    await update.message.reply_text("🗑 История диалога очищена.")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Да, сбросить всё", callback_data="reset:confirm"),
        InlineKeyboardButton("❌ Отмена", callback_data="reset:cancel"),
    ]])
    await update.message.reply_text(
        "⚠️ *Полный сброс удалит:*\n• Историю диалога\n• Все загруженные данные\n• Всю базу знаний\n\nПродолжить?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# ─────────────────────────────────────────────────────────────
# Обработка файлов
# ─────────────────────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    filename = doc.file_name or "file"
    user_id = update.effective_user.id

    msg = await update.message.reply_text(f"📥 Загружаю файл: {filename}...")

    file = await doc.get_file()
    file_bytes = bytes(await file.download_as_bytearray())

    try:
        if filename.lower().endswith(".csv"):
            rows = parse_csv_bytes(file_bytes)
        elif filename.lower().endswith((".xlsx", ".xls")):
            rows = parse_excel_bytes(file_bytes)
        else:
            await msg.edit_text("❌ Поддерживаются только CSV и Excel (.xlsx) файлы.")
            return
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка при разборе файла: {e}")
        return

    if not rows:
        await msg.edit_text("❌ Файл пустой или не удалось прочитать данные.")
        return

    channel = detect_channel_from_columns(rows)
    summary = summarize_data(rows)
    save_ad_data(user_id, filename, rows, channel=channel, summary=summary)

    ch_text = f"\nОпределён канал: *{channel}*" if channel else ""
    await msg.edit_text(
        f"✅ Файл загружен: *{filename}*\n"
        f"Строк данных: {len(rows)}{ch_text}\n\n"
        f"{summary}\n\n"
        f"Теперь можешь задать вопрос или ввести /analyze для полного анализа.",
        parse_mode="Markdown"
    )

    # Предлагаем уточнить канал, если не определился
    if not channel:
        context.user_data["pending_channel_for"] = filename
        await update.message.reply_text(
            "К какому рекламному каналу относятся эти данные?",
            reply_markup=channel_keyboard()
        )


# ─────────────────────────────────────────────────────────────
# Обработка текстовых сообщений
# ─────────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = context.user_data.get("state")

    # ── Состояния мастера добавления знаний ──
    if state == "waiting_knowledge_source":
        context.user_data["knowledge_source"] = text
        context.user_data["state"] = "waiting_knowledge_content"
        await update.message.reply_text(
            "Теперь вставь текст справки (можно скопировать из документации):",
        )
        return

    if state == "waiting_knowledge_content":
        source = context.user_data.get("knowledge_source", "Без названия")
        context.user_data["knowledge_content"] = text
        context.user_data["state"] = "waiting_knowledge_channel"
        await update.message.reply_text(
            f"К какому рекламному каналу относится эта справка?\n"
            f"(Или напиши «нет» если не относится к конкретному каналу)",
            reply_markup=channel_keyboard()
        )
        return

    if state == "waiting_knowledge_channel":
        source = context.user_data.get("knowledge_source", "Без названия")
        content = context.user_data.get("knowledge_content", "")
        channel = text if text.lower() not in ("нет", "-", "") else None
        save_knowledge(user_id, source, content, channel=channel)
        context.user_data["state"] = None
        await update.message.reply_text(
            f"✅ Справка добавлена в базу знаний!\nИсточник: {source}"
        )
        return

    # ── Попытка распарсить как CSV ──
    if "\n" in text and "," in text:
        try:
            rows = parse_csv_text(text)
            if rows and len(rows) > 1:
                channel = detect_channel_from_columns(rows)
                summary = summarize_data(rows)
                save_ad_data(user_id, "text_input.csv", rows, channel=channel, summary=summary)

                ch_text = f"\nКанал: {channel}" if channel else ""
                await update.message.reply_text(
                    f"✅ CSV-данные распознаны и сохранены!\n"
                    f"Строк: {len(rows)}{ch_text}\n{summary}"
                )
        except Exception:
            pass  # не CSV — идём дальше

    # ── Обычный диалог с GigaChat ──
    typing_msg = await update.message.reply_text("💭 Думаю...")

    try:
        reply = await ask_gigachat(user_id, text)
        await typing_msg.delete()

        # Разбиваем если ответ длинный
        chunks = [reply[i:i+4096] for i in range(0, len(reply), 4096)]
        for chunk in chunks:
            await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"GigaChat error for user {user_id}: {e}")
        await typing_msg.edit_text(f"❌ Ошибка GigaChat: {e}\n\nПопробуй позже.")


# ─────────────────────────────────────────────────────────────
# Callback-кнопки
# ─────────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data.startswith("channel:"):
        channel = data.split(":", 1)[1]
        if channel == "cancel":
            await query.message.edit_text("Отменено.")
            context.user_data["state"] = None
            return

        state = context.user_data.get("state")

        if state == "waiting_knowledge_channel":
            source = context.user_data.get("knowledge_source", "Без названия")
            content = context.user_data.get("knowledge_content", "")
            save_knowledge(user_id, source, content, channel=channel)
            context.user_data["state"] = None
            await query.message.edit_text(f"✅ Справка сохранена!\nИсточник: {source}\nКанал: {channel}")

        elif context.user_data.get("pending_channel_for"):
            filename = context.user_data["pending_channel_for"]
            # Обновляем канал последней загрузки
            from memory import get_conn
            conn = get_conn()
            conn.execute(
                "UPDATE ad_data SET channel=? WHERE user_id=? AND filename=? ORDER BY created_at DESC LIMIT 1",
                (channel, user_id, filename)
            )
            conn.commit()
            conn.close()
            context.user_data["pending_channel_for"] = None
            await query.message.edit_text(f"✅ Канал установлен: {channel} для файла {filename}")

    elif data.startswith("del_data:"):
        data_id = int(data.split(":")[1])
        delete_ad_data(user_id, data_id)
        await query.message.edit_text(f"🗑 Данные (id={data_id}) удалены.")

    elif data.startswith("del_know:"):
        source = data.split(":", 1)[1]
        delete_knowledge(user_id, source)
        await query.message.edit_text(f"🗑 Справка удалена: {source}")

    elif data == "reset:confirm":
        clear_history(user_id)
        # Удаляем все данные
        from memory import get_conn
        conn = get_conn()
        conn.execute("DELETE FROM ad_data WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM knowledge_base WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        context.user_data.clear()
        await query.message.edit_text("♻️ Полный сброс выполнен. Бот начинает с чистого листа.")

    elif data == "reset:cancel":
        await query.message.edit_text("Отменено.")


# ─────────────────────────────────────────────────────────────
# Запуск
# ─────────────────────────────────────────────────────────────

def main():
    init_db()
    logger.info("База данных инициализирована.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("add_knowledge", cmd_add_knowledge))
    app.add_handler(CommandHandler("add_url", cmd_add_url))
    app.add_handler(CommandHandler("upload_data", cmd_upload_data))
    app.add_handler(CommandHandler("my_data", cmd_my_data))
    app.add_handler(CommandHandler("my_knowledge", cmd_my_knowledge))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("clear_history", cmd_clear_history))
    app.add_handler(CommandHandler("reset", cmd_reset))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Бот запущен. Ожидаю сообщения...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
