import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# GigaChat
GIGACHAT_API_KEY = os.getenv("GIGACHAT_API_KEY", "")  # Credentials (Basic Auth)
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")  # или GIGACHAT_API_CORP

# Пути
DB_PATH = "data/bot.db"
CHROMA_PATH = "data/chroma_db"
UPLOADS_PATH = "data/uploads"

# Параметры модели
GIGACHAT_MODEL = "GigaChat-Pro"
MAX_TOKENS = 2000
TEMPERATURE = 0.3

# Размер контекста истории (количество последних сообщений)
HISTORY_LIMIT = 20

# Размер чанков для векторной БД
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Создать директории если нет
import os
for path in [DB_PATH, CHROMA_PATH, UPLOADS_PATH]:
    os.makedirs(os.path.dirname(path) if '/' in path else path, exist_ok=True)
