"""
Клиент для GigaChat API (Сбер).
Документация: https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-chat
"""

import os
import uuid
import time
import logging
import requests

logger = logging.getLogger(__name__)

GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
GIGACHAT_SCOPE = "GIGACHAT_API_PERS"  # или GIGACHAT_API_CORP для корп. аккаунта


class GigaChatClient:
    def __init__(self, credentials: str, model: str = "GigaChat-Pro"):
        """
        credentials: Authorization-ключ в формате Base64 (из личного кабинета Сбера)
        model: GigaChat, GigaChat-Pro, GigaChat-Max
        """
        self.credentials = credentials
        self.model = model
        self._access_token = None
        self._token_expires_at = 0

    def _get_token(self) -> str:
        """Получает/обновляет access token."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        response = requests.post(
            GIGACHAT_AUTH_URL,
            headers={
                "Authorization": f"Basic {self.credentials}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": GIGACHAT_SCOPE},
            verify=False,  # Сбер использует собственный CA
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        self._token_expires_at = data.get("expires_at", time.time() + 1800) / 1000
        return self._access_token

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Отправляет сообщения в GigaChat и возвращает текст ответа.

        messages: список {"role": "user"/"assistant", "content": "..."}
        system_prompt: системный промпт (добавляется первым)
        """
        token = self._get_token()

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        response = requests.post(
            GIGACHAT_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            verify=False,
            timeout=120,
        )

        if response.status_code != 200:
            logger.error(f"GigaChat error {response.status_code}: {response.text}")
            raise RuntimeError(f"GigaChat API error: {response.status_code} — {response.text}")

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def fetch_url_content(self, url: str) -> str:
        """Скачивает текстовый контент по URL (для справок с рекламных платформ)."""
        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (compatible; AdOptimizerBot/1.0)"
            })
            resp.raise_for_status()
            # Простая очистка HTML
            text = resp.text
            import re
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:10000]  # лимит 10k символов
        except Exception as e:
            raise RuntimeError(f"Не удалось загрузить URL: {e}")
