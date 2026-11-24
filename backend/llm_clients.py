"""Интеграции ИИ-провайдеров: облачный GigaChat API (Сбер) и локальная Ollama."""

from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from abc import ABC, abstractmethod
from typing import Any

from backend.config import AppConfig


class LLMClientError(RuntimeError):
    """Ошибка обращения к ИИ-провайдеру."""


class BaseLLMClient(ABC):
    """Общий интерфейс клиента языковой модели."""

    provider_name: str
    model_name: str

    @abstractmethod
    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict[str, Any]:
        """Отправляет промпт и возвращает распарсенный JSON-объект."""


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    """Извлекает JSON-объект из ответа модели (включая ответы внутри ```json ... ```)."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise LLMClientError("Модель вернула ответ, из которого не удалось извлечь JSON-объект.")


class GigaChatClient(BaseLLMClient):
    """
    Клиент Sber GigaChat API на базе OAuth2 + Chat Completions.
    Ключ авторизации берётся строго из переменной окружения GIGACHAT_AUTH_KEY.
    """

    OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    def __init__(
        self,
        auth_key: str,
        scope: str = "GIGACHAT_API_PERS",
        model: str = "GigaChat",
        timeout: int = 30,
        verify_ssl: bool = True,
        ca_bundle: str = "",
    ) -> None:
        if not auth_key:
            raise LLMClientError(
                "Не задан ключ GIGACHAT_AUTH_KEY. Укажите его в .env или переключитесь на LLM_PROVIDER=ollama."
            )
        self.provider_name = "gigachat"
        self.model_name = model
        self._auth_key = auth_key
        self._scope = scope
        self._timeout = timeout
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._ssl_context = self._build_ssl_context(verify_ssl, ca_bundle)

    @staticmethod
    def _build_ssl_context(verify_ssl: bool, ca_bundle: str) -> ssl.SSLContext:
        if not verify_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        if ca_bundle:
            return ssl.create_default_context(cafile=ca_bundle)
        return ssl.create_default_context()

    def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        form_data = urllib.parse.urlencode({"scope": self._scope}).encode("utf-8")
        req = urllib.request.Request(
            self.OAUTH_URL,
            data=form_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {self._auth_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl_context) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMClientError(
                f"Ошибка OAuth GigaChat (HTTP {exc.code}). Проверьте GIGACHAT_AUTH_KEY и GIGACHAT_SCOPE."
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(
                f"Не удалось подключиться к OAuth GigaChat ({exc.reason}). "
                "При ошибке сертификата установите сертификат Минцифры или укажите GIGACHAT_CA_BUNDLE."
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMClientError(
                f"Превышено время ожидания OAuth GigaChat ({self._timeout} с)."
            ) from exc

        token = data.get("access_token")
        if not token:
            raise LLMClientError("GigaChat OAuth не вернул access_token.")
        expires_at_ms = data.get("expires_at")
        self._access_token = str(token)
        if isinstance(expires_at_ms, (int, float)) and expires_at_ms > 1_000_000_000_000:
            self._token_expires_at = float(expires_at_ms) / 1000.0
        else:
            self._token_expires_at = now + 25 * 60
        return self._access_token

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict[str, Any]:
        token = self._get_access_token()
        payload = json.dumps(
            {
                "model": self.model_name,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            self.CHAT_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl_context) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMClientError(f"GigaChat API вернул HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(f"Сетевая ошибка GigaChat API: {exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMClientError(
                f"Превышено время ожидания ответа GigaChat API ({self._timeout} с)."
            ) from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Неожиданный формат ответа GigaChat API.") from exc

        return _extract_json_object(str(content))


class OllamaClient(BaseLLMClient):
    """
    Клиент локальной нейросети через Ollama (https://ollama.com).
    Позволяет жюри запустить проверочный режим с ИИ полностью локально и без покупки аккаунта.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:7b",
        timeout: int = 180,
    ) -> None:
        self.provider_name = "ollama"
        self.model_name = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict[str, Any]:
        url = f"{self._base_url}/api/chat"
        payload = json.dumps(
            {
                "model": self.model_name,
                "format": "json",
                "stream": False,
                "keep_alive": "10m",
                "options": {"temperature": temperature},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMClientError(
                f"Ollama вернула HTTP {exc.code}. Проверьте, скачана ли модель «{self.model_name}» (ollama pull {self.model_name})."
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(
                f"Локальный сервер Ollama недоступен по адресу {self._base_url} ({exc.reason})."
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMClientError(
                f"Превышено время ожидания ответа Ollama ({self._timeout} с). "
                "При первом запуске модель может долго загружаться в память — повторите запрос или выберите более лёгкую модель (например, qwen2.5:3b)."
            ) from exc

        message = body.get("message") if isinstance(body, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            raise LLMClientError("Ollama вернула пустой ответ.")
        return _extract_json_object(str(content))


def create_llm_client(config: AppConfig, provider_override: str | None = None) -> BaseLLMClient | None:
    """Создаёт клиент ИИ согласно настройкам. Возвращает None для режима rules."""
    provider = (provider_override or config.llm_provider).strip().lower()
    if provider == "rules":
        return None
    if provider == "gigachat":
        return GigaChatClient(
            auth_key=config.gigachat_auth_key,
            scope=config.gigachat_scope,
            model=config.gigachat_model,
            timeout=max(20, config.http_timeout_seconds),
            verify_ssl=config.gigachat_verify_ssl,
            ca_bundle=config.gigachat_ca_bundle,
        )
    if provider == "ollama":
        return OllamaClient(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
            timeout=max(180, config.http_timeout_seconds),
        )
    raise LLMClientError(f"Неизвестный ИИ-провайдер: {provider}")
