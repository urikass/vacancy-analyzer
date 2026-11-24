"""Клиент API портала «Работа в России» (регион 39) и парсер локального JSON."""

from __future__ import annotations

import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


ALLOWED_API_HOSTS = {"opendata.trudvsem.ru"}


class TrudvsemAPIError(RuntimeError):
    """Исключение при недоступности или некорректном ответе API «Работа в России»."""


def validate_source_url(url: str, allow_custom_hosts: bool = False) -> str:
    """Проверяет URL источника на безопасную схему и допустимый хост (защита от SSRF)."""
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise TrudvsemAPIError(
            f"Недопустимая схема URL «{parsed.scheme}». Разрешены только http и https."
        )
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise TrudvsemAPIError("URL источника не содержит имени хоста.")

    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise TrudvsemAPIError("Обращение к локальному адресу запрещено для URL источника.")

    try:
        ip_obj = ipaddress.ip_address(hostname)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            raise TrudvsemAPIError("Обращение к приватным или служебным IP-адресам запрещено.")
    except ValueError:
        # Это доменное имя, не IP
        pass

    if not allow_custom_hosts and hostname not in ALLOWED_API_HOSTS:
        raise TrudvsemAPIError(
            f"Хост «{hostname}» не входит в список разрешённых ({', '.join(sorted(ALLOWED_API_HOSTS))})."
        )

    return url.strip()


def extract_vacancies_from_payload(payload: Any) -> list[dict[str, Any]]:
    """Извлекает список словарей вакансий из формата ответа API «Работа в России»."""
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, dict) and isinstance(results.get("vacancies"), list):
            items = results["vacancies"]
        elif isinstance(payload.get("vacancies"), list):
            items = payload["vacancies"]
        elif "vacancy" in payload and isinstance(payload["vacancy"], dict):
            items = [payload]
        else:
            raise ValueError(
                "Не удалось найти массив вакансий (ожидается results.vacancies или vacancies)."
            )
    else:
        raise ValueError("Корневой элемент JSON должен быть объектом или массивом.")

    vacancies: list[dict[str, Any]] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        vacancy_obj = entry.get("vacancy") if isinstance(entry.get("vacancy"), dict) else entry
        if isinstance(vacancy_obj, dict):
            vacancies.append(vacancy_obj)
    return vacancies


def load_vacancies_from_file(file_path: str | Path) -> list[dict[str, Any]]:
    """Загружает и разбирает локальный JSON-файл в формате ответов API."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Файл с вакансиями не найден: {path}")
    raw_text = path.read_text(encoding="utf-8-sig")
    payload = json.loads(raw_text)
    return extract_vacancies_from_payload(payload)


def _default_http_get_json(url: str, timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "TransparentVacancyRegion39/1.0 (+KantKod)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status >= 400:
                raise TrudvsemAPIError(f"API вернул HTTP {status} по адресу {url}")
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        raise TrudvsemAPIError(f"HTTP ошибка {exc.code} при обращении к API: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise TrudvsemAPIError(f"Не удалось подключиться к API «Работа в России»: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise TrudvsemAPIError(f"Превышено время ожидания ответа API ({timeout} с).") from exc
    except json.JSONDecodeError as exc:
        raise TrudvsemAPIError(f"API вернул некорректный JSON: {exc}") from exc


def fetch_vacancies_paginated(
    api_url: str,
    max_vacancies: int = 40,
    page_size: int = 20,
    timeout: int = 20,
    http_get: Callable[[str, int], dict[str, Any]] | None = None,
    allow_custom_hosts: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """
    Загружает вакансии региона 39 постранично (минимум 2 страницы, если лимит и объём позволяют).
    Возвращает кортеж: (список уникальных вакансий, число загруженных страниц).
    """
    validated_url = validate_source_url(api_url, allow_custom_hosts=allow_custom_hosts)
    getter = http_get or _default_http_get_json

    max_vacancies = max(1, max_vacancies)
    effective_page_size = max(1, min(page_size, 100))
    # Если лимит позволяет получить больше 1 вакансии и page_size >= max_vacancies,
    # автоматически делим страницу пополам, чтобы обработать минимум 2 страницы.
    if max_vacancies >= 2 and effective_page_size >= max_vacancies:
        effective_page_size = max(1, max_vacancies // 2)

    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    offset = 0
    pages_fetched = 0

    while len(collected) < max_vacancies:
        remaining = max_vacancies - len(collected)
        limit = min(effective_page_size, remaining)
        separator = "&" if "?" in validated_url else "?"
        page_url = f"{validated_url}{separator}offset={offset}&limit={limit}"

        payload = getter(page_url, timeout)
        pages_fetched += 1

        page_items = extract_vacancies_from_payload(payload)
        if not page_items:
            break

        for vacancy in page_items:
            vid = str(vacancy.get("id") or "").strip()
            if vid and vid in seen_ids:
                continue
            if vid:
                seen_ids.add(vid)
            collected.append(vacancy)
            if len(collected) >= max_vacancies:
                break

        meta = payload.get("meta") if isinstance(payload, dict) else {}
        total_raw = meta.get("total") if isinstance(meta, dict) else None
        try:
            total_available = int(total_raw) if total_raw is not None else None
        except (TypeError, ValueError):
            total_available = None

        offset += len(page_items)
        if len(page_items) < limit:
            break
        if total_available is not None and offset >= total_available:
            break

    return collected, pages_fetched
