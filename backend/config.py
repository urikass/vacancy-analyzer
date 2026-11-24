"""Загрузка и валидация конфигурации сервиса из .env и переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_file(env_path: Path) -> None:
    """Читает локальный .env без обязательной установки сторонних библиотек."""
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
        ):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


def _parse_int(value: str | None, default: int, minimum: int = 1, maximum: int = 5000) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value.strip())
    except ValueError:
        return default
    return max(minimum, min(maximum, parsed))


@dataclass(frozen=True)
class AppConfig:
    """Параметры работы анализатора, планировщика и ИИ-провайдеров."""

    api_url: str = "http://opendata.trudvsem.ru/api/v1/vacancies/region/39"
    max_vacancies: int = 40
    page_size: int = 20
    http_timeout_seconds: int = 20
    schedule_interval_minutes: int = 60
    schedule_cron: str = "0 * * * *"

    # Провайдер ИИ: "gigachat" | "ollama" | "rules"
    llm_provider: str = "ollama"

    # GigaChat API (Сбер)
    gigachat_auth_key: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat"
    gigachat_verify_ssl: bool = True
    gigachat_ca_bundle: str = ""

    # Локальный запуск через Ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"

    # Пути вывода
    output_dir: str = "output"
    last_report_path: str = "output/latest_report.json"

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "AppConfig":
        """Собирает конфигурацию из файла .env и переменных окружения."""
        if env_file is not None:
            _load_dotenv_file(Path(env_file))
        else:
            _load_dotenv_file(Path.cwd() / ".env")

        provider = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()
        if provider not in ("gigachat", "ollama", "rules"):
            provider = "ollama"

        return cls(
            api_url=os.environ.get(
                "TRUDVSEM_API_URL",
                "http://opendata.trudvsem.ru/api/v1/vacancies/region/39",
            ).strip(),
            max_vacancies=_parse_int(os.environ.get("MAX_VACANCIES"), 40, minimum=1, maximum=1000),
            page_size=_parse_int(os.environ.get("PAGE_SIZE"), 20, minimum=1, maximum=100),
            http_timeout_seconds=_parse_int(
                os.environ.get("HTTP_TIMEOUT_SECONDS"), 20, minimum=3, maximum=120
            ),
            schedule_interval_minutes=_parse_int(
                os.environ.get("SCHEDULE_INTERVAL_MINUTES"), 60, minimum=1, maximum=10080
            ),
            schedule_cron=os.environ.get("SCHEDULE_CRON", "0 * * * *").strip(),
            llm_provider=provider,
            gigachat_auth_key=os.environ.get("GIGACHAT_AUTH_KEY", "").strip(),
            gigachat_scope=os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip(),
            gigachat_model=os.environ.get("GIGACHAT_MODEL", "GigaChat").strip(),
            gigachat_verify_ssl=_parse_bool(os.environ.get("GIGACHAT_VERIFY_SSL"), True),
            gigachat_ca_bundle=os.environ.get("GIGACHAT_CA_BUNDLE", "").strip(),
            ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/"),
            ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5:7b").strip(),
            output_dir=os.environ.get("OUTPUT_DIR", "output").strip(),
            last_report_path=os.environ.get("LAST_REPORT_PATH", "output/latest_report.json").strip(),
        )
