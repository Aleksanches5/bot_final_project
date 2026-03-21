import logging
import os
from telegram import Update
from telegram.ext import ContextTypes
from services.file_parser import (
    parse_csv, parse_excel, parse_txt_or_pdf,
    split_text_into_chunks, detect_ad_channel
)
from services.vector_store import add_texts
from database.db import save_document, save_ad_data
from config import UPLOADS_PATH

logger = logging.getLogger(__name__)

# Максимальный размер файла (20 МБ)
MAX_FILE_SIZE = 20 * 1024 * 1024


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document
    filename = doc.file_name or "file"
    mime = doc.mime_type or ""

    if doc.file_size > MAX_FILE_SIZE:
        await update.message.reply_text("❌ Файл слишком большой (максимум 20 МБ).")
        return

    await update.message.reply_text(f"⏳ Загружаю файл `{filename}`...", )

    try:
        # Скачать файл
        file = await context.bot.get_file(doc.file_id)
        file_bytes = await file.download_as_bytearray()
        file_bytes = bytes(file_bytes)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # ─── CSV ─────────────────────────────────────────────────────────────
        if ext == "csv" or "csv" in mime:
            text, data = parse_csv(file_bytes, filename)
            channel = detect_ad_channel(data.get("columns", []), text)
            chunks = split_text_into_chunks(text)
            chroma_ids = add_texts(
                user_id, chunks,
                [{"source": filename, "type": "ad_data", "channel": channel}] * len(chunks)
            )
            save_document(user_id, filename, "CSV данные", text[:500], chroma_ids)
            save_ad_data(user_id, filename, channel, data)

            await update.message.reply_text(
                f"✅ **CSV загружен: `{filename}`**\n\n"
                f"📌 Канал: {channel}\n"
                f"📊 Строк: {data['shape'][0]}, Столбцов: {data['shape'][1]}\n"
                f"📋 Метрики: {', '.join(data['columns'][:8])}\n\n"
                f"Теперь можешь спросить: _«Проанализируй мои кампании»_",
                
            )

        # ─── Excel ───────────────────────────────────────────────────────────
        elif ext in ("xlsx", "xls") or "excel" in mime or "spreadsheet" in mime:
            text, data = parse_excel(file_bytes, filename)
            # Определяем канал по всем листам
            all_columns = []
            for sheet_data in data.values():
                all_columns.extend(sheet_data.get("columns", []))
            channel = detect_ad_channel(all_columns, text)

            chunks = split_text_into_chunks(text)
            chroma_ids = add_texts(
                user_id, chunks,
                [{"source": filename, "type": "ad_data", "channel": channel}] * len(chunks)
            )
            save_document(user_id, filename, "Excel данные", text[:500], chroma_ids)
            save_ad_data(user_id, filename, channel, data)

            sheets = list(data.keys())
            await update.message.reply_text(
                f"✅ **Excel загружен: `{filename}`**\n\n"
                f"📌 Канал: {channel}\n"
                f"📋 Листы: {', '.join(sheets)}\n\n"
                f"Теперь можешь спросить: _«Проанализируй мои кампании»_",
                
            )

        # ─── PDF / TXT ────────────────────────────────────────────────────────
        elif ext in ("pdf", "txt", "md") or "pdf" in mime or "text" in mime:
            text = parse_txt_or_pdf(file_bytes, filename, mime)
            if not text.strip():
                await update.message.reply_text("❌ Файл пустой или не удалось извлечь текст.")
                return

            chunks = split_text_into_chunks(text)
            chroma_ids = add_texts(
                user_id, chunks,
                [{"source": filename, "type": "knowledge", "channel": "general"}] * len(chunks)
            )
            save_document(user_id, filename, "Справка", text[:500], chroma_ids)

            await update.message.reply_text(
                f"✅ **Справка загружена: `{filename}`**\n\n"
                f"📚 Добавлено {len(chunks)} фрагментов в базу знаний.\n\n"
                f"Теперь бот будет использовать эту информацию при анализе.",
                
            )

        else:
            await update.message.reply_text(
                f"⚠️ Формат `{ext}` не поддерживается.\n"
                "Поддерживаемые форматы: CSV, Excel (.xlsx/.xls), PDF, TXT",
                
            )

    except Exception as e:
        logger.error(f"Ошибка обработки файла {filename}: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка при обработке файла: {str(e)}\n"
            "Проверь формат файла и попробуй снова."
        )
