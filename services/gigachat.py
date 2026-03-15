import logging
import requests
from config import GIGACHAT_API_KEY, MAX_TOKENS, TEMPERATURE

# Отключить предупреждения об SSL — Сбер использует самоподписанный сертификат
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

GROQ_API_KEY = GIGACHAT_API_KEY  # переиспользуем переменную
GROQ_MODEL = "llama-3.3-70b-versatile"  # мощная бесплатная модель


def chat(messages: list[dict], system_prompt: str = None) -> str:
    """Отправить сообщения в Groq API и получить ответ."""

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

    logger.info(f"Запрос к Groq API, модель={GROQ_MODEL}")

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        logger.info(f"Ответ Groq API: HTTP {resp.status_code}")
        if resp.status_code != 200:
            logger.error(f"Тело ошибки: {resp.text[:300]}")
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP ошибка Groq: {e}, тело: {e.response.text[:300]}")
        raise
    except Exception as e:
        logger.error(f"Ошибка запроса Groq: {e}")
        raise


def build_system_prompt(knowledge_chunks: list[str] = None, ad_data_summary: str = None) -> str:
    base = """Ты — экспертный аналитик рекламных кампаний. Твоя задача — анализировать рекламные метрики и давать конкретные рекомендации по оптимизации.

Формат ответа:
📊 АНАЛИЗ МЕТРИК
— Ключевые показатели и их оценка

🔍 ВЫВОДЫ
— Что работает хорошо / плохо и почему

⚡ РЕКОМЕНДАЦИИ ПО ПРИОРИТЕТАМ
1. [ВЫСОКИЙ] Конкретное действие
2. [СРЕДНИЙ] Конкретное действие
3. [НИЗКИЙ] Конкретное действие

💡 ОЖИДАЕМЫЙ ЭФФЕКТ
— Что даст каждое действие

Всегда опирайся на конкретные данные. Отвечай на русском языке."""

    if knowledge_chunks:
        knowledge = "\n\n".join(knowledge_chunks)
        base += f"\n\n---\nСПРАВОЧНАЯ ИНФОРМАЦИЯ О РЕКЛАМНЫХ КАНАЛАХ:\n{knowledge}"

    if ad_data_summary:
        base += f"\n\n---\nЗАГРУЖЕННЫЕ РЕКЛАМНЫЕ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:\n{ad_data_summary}"

    return base