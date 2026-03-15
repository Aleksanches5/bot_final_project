import logging
import requests
import time
import uuid
import urllib3
from typing import Optional
from config import GIGACHAT_API_KEY, GIGACHAT_SCOPE, GIGACHAT_MODEL, MAX_TOKENS, TEMPERATURE

# Отключить предупреждения об SSL — Сбер использует самоподписанный сертификат
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_access_token: Optional[str] = None
_token_expires_at: float = 0


def _get_access_token() -> str:
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

    logger.info(f"Запрос токена GigaChat, scope={GIGACHAT_SCOPE}")
    logger.info(f"API key (первые 10 символов): {GIGACHAT_API_KEY[:10]}...")

    try:
        resp = requests.post(
            url, headers=headers, data=data,
            verify=False, timeout=30
        )
        logger.info(f"Ответ авторизации: HTTP {resp.status_code}")
        logger.info(f"Тело ответа: {resp.text[:300]}")
        resp.raise_for_status()
        result = resp.json()
        _access_token = result["access_token"]
        _token_expires_at = result.get("expires_at", 0) / 1000
        logger.info("Токен GigaChat успешно получен")
        return _access_token
    except Exception as e:
        logger.error(f"Ошибка получения токена GigaChat: {e}")
        raise


def chat(messages: list[dict], system_prompt: str = None) -> str:
    token = _get_access_token()

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
        resp = requests.post(
            url, headers=headers, json=payload,
            verify=False, timeout=60
        )
        logger.info(f"Ответ GigaChat: HTTP {resp.status_code}")
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            global _access_token
            _access_token = None
            return chat(messages, system_prompt)
        logger.error(f"HTTP ошибка GigaChat: {e}, тело: {e.response.text[:200]}")
        raise
    except Exception as e:
        logger.error(f"Ошибка запроса GigaChat: {e}")
        raise


def build_system_prompt(knowledge_chunks: list[str] = None, ad_data_summary: str = None) -> str:
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

Всегда опирайся на конкретные данные. Отвечай на русском языке."""

    if knowledge_chunks:
        knowledge = "\n\n".join(knowledge_chunks)
        base += f"\n\n---\nСПРАВОЧНАЯ ИНФОРМАЦИЯ О РЕКЛАМНЫХ КАНАЛАХ:\n{knowledge}"

    if ad_data_summary:
        base += f"\n\n---\nЗАГРУЖЕННЫЕ РЕКЛАМНЫЕ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:\n{ad_data_summary}"

    return base