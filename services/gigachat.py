import logging
import requests
from config import GIGACHAT_API_KEY, MAX_TOKENS, TEMPERATURE

# Отключить предупреждения об SSL — Сбер использует самоподписанный сертификат
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

GROQ_API_KEY = GIGACHAT_API_KEY
GROQ_MODEL = "llama-3.3-70b-versatile"


def chat(messages: list[dict], system_prompt: str = None) -> str:
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": full_messages,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE
    }

    logger.info(f"Запрос к Groq API")
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload, timeout=60
        )
        logger.info(f"Ответ Groq: HTTP {resp.status_code}")
        if resp.status_code != 200:
            logger.error(f"Ошибка: {resp.text[:300]}")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Ошибка Groq: {e}")
        raise


def build_system_prompt(knowledge_chunks: list[str] = None, ad_data_summary: str = None) -> str:
    base = """Ты — экспертный аналитик рекламных кампаний. Анализируй метрики и давай конкретные рекомендации по оптимизации.

Формат ответа:
📊 АНАЛИЗ МЕТРИК — ключевые показатели
🔍 ВЫВОДЫ — что работает / не работает
⚡ РЕКОМЕНДАЦИИ: 1.[ВЫСОКИЙ] 2.[СРЕДНИЙ] 3.[НИЗКИЙ]
💡 ОЖИДАЕМЫЙ ЭФФЕКТ

Отвечай на русском языке."""

    if knowledge_chunks:
        base += f"\n\n---\nСПРАВКИ О КАНАЛАХ:\n" + "\n\n".join(knowledge_chunks)
    if ad_data_summary:
        base += f"\n\n---\nДАННЫЕ ПОЛЬЗОВАТЕЛЯ:\n{ad_data_summary}"
    return base