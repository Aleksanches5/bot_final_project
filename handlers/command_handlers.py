import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.db import (
    upsert_user_profile, clear_history, get_user_stats,
    get_user_documents, get_user_ad_data
)
from services.vector_store import delete_collection, get_collection_size

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user_profile(user.id, user.username or user.first_name)

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я — аналитик рекламных кампаний на базе GigaChat.\n\n"
        "🔹 **Что я умею:**\n"
        "• Анализировать рекламные метрики (CTR, CPC, CPM, ROAS и др.)\n"
        "• Загружать справки с рекламных кабинетов (ссылки или файлы)\n"
        "• Принимать данные в формате CSV, Excel, TXT\n"
        "• Давать конкретные рекомендации по оптимизации\n\n"
        "🔹 **Как начать:**\n"
        "1️⃣ Загрузи справку канала: пришли ссылку или файл\n"
        "2️⃣ Загрузи данные кампаний: пришли CSV/Excel файл\n"
        "3️⃣ Задай вопрос или попроси анализ\n\n"
        "📌 /help — подробная справка\n"
        "📌 /status — что уже загружено\n"
        "📌 /reset — очистить всю память",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Справка по боту**\n\n"
        "**Загрузка справок о каналах:**\n"
        "• Отправь ссылку на страницу справки (например, help.direct.yandex.ru/...)\n"
        "• Или загрузи файл с описанием канала (.txt, .pdf)\n\n"
        "**Загрузка рекламных данных:**\n"
        "• Отправь .csv или .xlsx/.xls файл с метриками\n"
        "• Поддерживаемые метрики: CTR, CPC, CPM, CR, ROAS, CPA, показы, клики, расходы и др.\n\n"
        "**Анализ:**\n"
        "• Задай вопрос текстом: _«Почему высокий CPC?»_\n"
        "• Попроси анализ: _«Проанализируй мои кампании»_\n"
        "• Попроси рекомендации: _«Что оптимизировать в первую очередь?»_\n\n"
        "**Команды:**\n"
        "/start — приветствие\n"
        "/status — статус загруженных данных\n"
        "/reset — очистить всю память (данные + история)\n"
        "/help — эта справка",
        parse_mode="Markdown"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = get_user_stats(user_id)
    docs = get_user_documents(user_id)
    ad_data = get_user_ad_data(user_id)
    vector_count = get_collection_size(user_id)

    # Список документов
    docs_list = ""
    if docs:
        for d in docs[-5:]:  # последние 5
            docs_list += f"  • {d['filename']} ({d['doc_type']}) — {d['created_at'][:10]}\n"
    else:
        docs_list = "  _(нет загруженных справок)_\n"

    # Список данных
    data_list = ""
    if ad_data:
        for d in ad_data[-5:]:
            channel = d.get("channel", "?")
            data_list += f"  • {d['source_file']} [{channel}] — {d['created_at'][:10]}\n"
    else:
        data_list = "  _(нет рекламных данных)_\n"

    await update.message.reply_text(
        f"📊 **Статус твоей базы знаний**\n\n"
        f"🧠 Векторов в памяти: {vector_count}\n"
        f"💬 Сообщений в истории: {stats['messages']}\n\n"
        f"📚 **Загруженные справки:**\n{docs_list}\n"
        f"📈 **Рекламные данные:**\n{data_list}",
        parse_mode="Markdown"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_history(user_id)
    delete_collection(user_id)

    await update.message.reply_text(
        "🗑️ Всё очищено: история диалогов и база знаний удалены.\n"
        "Можешь начать заново — загрузи справки и данные."
    )
