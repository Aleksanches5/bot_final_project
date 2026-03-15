import os

# load_dotenv только если есть .env файл (локальная разработка)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()

# GigaChat
GIGACHAT_API_KEY = os.environ.get("GIGACHAT_API_KEY", "").strip()
GIGACHAT_SCOPE = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()

# Проверка токена при старте
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан! Добавьте переменную окружения.")
if not GIGACHAT_API_KEY:
    raise ValueError("GIGACHAT_API_KEY не задан! Добавьте переменную окружения.")

# Пути
DB_PATH = "data/bot.db"
CHROMA_PATH = "data/chroma_db"
UPLOADS_PATH = "data/uploads"

# Параметры модели
GIGACHAT_MODEL = "GigaChat-Pro"
MAX_TOKENS = 2000
TEMPERATURE = 0.3

# Размер контекста истории
HISTORY_LIMIT = 20

# Размер чанков для векторной БД
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Создать директории если нет
for path in ["data", CHROMA_PATH, UPLOADS_PATH]:
    os.makedirs(path, exist_ok=True)
