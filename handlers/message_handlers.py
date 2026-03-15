import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from services.gigachat import chat, build_system_prompt
from services.vector_store import search_relevant, add_texts
from services.file_parser import fetch_url_content, split_text_into_chunks
from database.db import add_message, get_history, get_user_ad_data, save_document

logger = logging.getLogger(__name__)
URL_RE = re.compile(r"https?://[^\s]+")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    urls = URL_RE.findall(text)
    if urls:
        await _handle_urls(update, context, user_id, urls)
        return

    await _handle_chat(update, context, user_id, text)


async def _handle_urls(update, context, user_id: int, urls: list[str]):
    msg = await update.message.reply_text(f"🔗 Загружаю {len(urls)} ссылку(-и)...")
    loaded = []
    failed = []
    for url in urls:
        try:
            content = fetch_url_content(url)
            if len(content) < 100:
                failed.append(url)
                continue
            chunks = split_text_into_chunks(content)
            chroma_ids = add_texts(
                user_id, chunks,
                [{"source": url, "type": "knowledge", "channel": "web"}] * len(chunks)
            )
            domain = url.split("/")[2] if "/" in url else url
            save_document(user_id, domain, "Веб-справка", content[:500], chroma_ids)
            loaded.append((url, len(chunks)))
        except Exception as e:
            logger.error(f"Ошибка загрузки {url}: {e}")
            failed.append(url)

    result_lines = ["📚 *Результат загрузки ссылок:*\n"]
    for url, chunks_count in loaded:
        result_lines.append(f"✅ {url}\n   Добавлено {chunks_count} фрагментов")
    for url in failed:
        result_lines.append(f"❌ {url}\n   Не удалось загрузить")
    result_lines.append("\nТеперь бот учитывает эти данные при анализе.")

    await context.bot.edit_message_text(
        "\n".join(result_lines),
        chat_id=update.effective_chat.id,
        message_id=msg.message_id,
        parse_mode="Markdown"
    )


async def _handle_chat(update, context, user_id: int, user_text: str):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Сохранить сообщение
    add_message(user_id, "user", user_text)

    # RAG поиск
    try:
        relevant_chunks = search_relevant(user_id, user_text, n_results=5)
    except Exception as e:
        logger.error(f"Ошибка RAG поиска: {e}")
        relevant_chunks = []

    # Сводка рекламных данных
    try:
        ad_data = get_user_ad_data(user_id)
        ad_summary = _build_ad_data_summary(ad_data)
    except Exception as e:
        logger.error(f"Ошибка получения ad_data: {e}")
        ad_summary = ""

    system_prompt = build_system_prompt(
        knowledge_chunks=relevant_chunks if relevant_chunks else None,
        ad_data_summary=ad_summary if ad_summary else None
    )

    history = get_history(user_id, limit=20)

    # Уведомить что думаем
    thinking_msg = await update.message.reply_text("⏳ Анализирую данные, подожди...")

    try:
        response = chat(history, system_prompt=system_prompt)
        add_message(user_id, "assistant", response)

        # Удалить "думаю..."
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=thinking_msg.message_id
        )

        # Отправить ответ частями если длинный
        if len(response) <= 4096:
            await update.message.reply_text(response, parse_mode="Markdown")
        else:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for i, part in enumerate(parts):
                prefix = f"_(часть {i+1}/{len(parts)})_\n\n" if len(parts) > 1 else ""
                await update.message.reply_text(prefix + part, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка GigaChat для user {user_id}: {e}", exc_info=True)
        await context.bot.edit_message_text(
            f"❌ Ошибка при обращении к GigaChat:\n`{str(e)}`\n\nПопробуй снова.",
            chat_id=update.effective_chat.id,
            message_id=thinking_msg.message_id,
            parse_mode="Markdown"
        )


def _build_ad_data_summary(ad_data: list[dict]) -> str:
    if not ad_data:
        return ""
    lines = []
    for entry in ad_data[-10:]:
        channel = entry.get("channel", "?")
        source = entry.get("source_file", "?")
        data = entry.get("data_json", {})
        if isinstance(data, dict) and not data.get("columns"):
            sheet_names = list(data.keys())
            if sheet_names:
                data = data[sheet_names[0]]
        columns = data.get("columns", [])
        stats = data.get("numeric_stats", {})
        shape = data.get("shape", [0, 0])
        lines.append(f"\n📊 {source} ({channel})")
        lines.append(f"  Строк: {shape[0]}, метрики: {', '.join(str(c) for c in columns[:8])}")
        for col, s in list(stats.items())[:6]:
            lines.append(
                f"  {col}: сумма={s['sum']}, среднее={s['mean']}, "
                f"мин={s['min']}, макс={s['max']}"
            )
    return "\n".join(lines)
