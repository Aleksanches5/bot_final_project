import logging
import requests
import time
import uuid
import base64
from typing import Optional
from config import GIGACHAT_API_KEY, GIGACHAT_SCOPE, GIGACHAT_MODEL, MAX_TOKENS, TEMPERATURE

logger = logging.getLogger(__name__)

# Токен и его время истечения
_access_token: Optional[str] = None
_token_expires_at: float = 0


def _get_access_token() -> str:
    """Получить OAuth-токен GigaChat (кэшируется до истечения)."""
    global _access_token, _token_expires_at

    if _access_token and time.time() < _token_expires_at - 60:
        return _access_token

    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {GIGACHAT_API_KEY}"
    }
    data = {"scope": GIGACHAT_SCOPE}

    try:
        resp = requests.post(url, headers=headers, data=data, verify=False, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        _access_token = result["access_token"]
        # expires_at в миллисекундах
        _token_expires_at = result.get("expires_at", 0) / 1000
        logger.info("Токен GigaChat получен")
        return _access_token
    except Exception as e:
        logger.error(f"Ошибка получения токена GigaChat: {e}")
        raise


def chat(messages: list[dict], system_prompt: str = None) -> str:
    """
    Отправить сообщения в GigaChat и получить ответ.
    
    messages: список {"role": "user"/"assistant", "content": "..."}
    system_prompt: системный промпт
    """
    token = _get_access_token()

    # Формируем список сообщений
    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "model": GIGACHAT_MODEL,
        "messages": full_messages,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "stream": False
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        answer = result["choices"][0]["message"]["content"]
        return answer
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            # Токен истёк — сбросить и попробовать ещё раз
            global _access_token
            _access_token = None
            return chat(messages, system_prompt)
        logger.error(f"HTTP ошибка GigaChat: {e}")
        raise
    except Exception as e:
        logger.error(f"Ошибка запроса GigaChat: {e}")
        raise


def build_system_prompt(knowledge_chunks: list[str] = None, ad_data_summary: str = None) -> str:
    """Собрать системный промпт с контекстом из базы знаний."""
    base = """Ты — экспертный аналитик рекламных кампаний. Твоя задача — анализировать рекламные метрики и давать конкретные рекомендации по оптимизации.

Формат ответа:
📊 **АНАЛИЗ МЕТРИК**
— Ключевые показатели и их оценка

🔍 **ВЫВОДЫ**
— Что работает хорошо / плохо и почему

⚡ **РЕКОМЕНДАЦИИ ПО ПРИОРИТЕТАМ**
1. [ВЫСОКИЙ] Конкретное действие
2. [СРЕДНИЙ] Конкретное действие
3. [НИЗКИЙ] Конкретное действие

💡 **ОЖИДАЕМЫЙ ЭФФЕКТ**
— Что даст каждое действие

Всегда опирайся на конкретные данные. Не давай общих советов без привязки к цифрам.
Отвечай на русском языке."""

    if knowledge_chunks:
        knowledge = "\n\n".join(knowledge_chunks)
        base += f"\n\n---\nСПРАВОЧНАЯ ИНФОРМАЦИЯ О РЕКЛАМНЫХ КАНАЛАХ:\n{knowledge}"

    if ad_data_summary:
        base += f"\n\n---\nЗАГРУЖЕННЫЕ РЕКЛАМНЫЕ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:\n{ad_data_summary}"

    return base
