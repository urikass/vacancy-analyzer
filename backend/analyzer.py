"""Гибридный анализатор вакансий (правила + ИИ) и сохранение отчётов."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import AppConfig
from backend.llm_clients import BaseLLMClient, LLMClientError, create_llm_client
from backend.models import (
    AnalysisReport,
    Issue,
    VALID_ISSUE_TYPES,
    VALID_TOPICS,
    VacancyReportItem,
    VacancySummary,
)
from backend.rules import normalize_vacancy, run_rule_checks
from backend.trudvsem_client import (
    TrudvsemAPIError,
    fetch_vacancies_paginated,
    load_vacancies_from_file,
)


AI_SYSTEM_PROMPT = """Ты — редактор-аналитик вакансий портала «Работа в России» (Калининградская область, регион 39).
Твоя задача — оценить, насколько понятно описаны условия работы, чтобы редактор мог задать работодателю конкретные уточнения.

Правила анализа (строго соблюдай):
1. Проверяй 7 тем: "название должности", "обязанности", "требования", "оплата", "график", "место работы", "тип занятости".
2. Учитывай И текст описания, И структурированные поля API. Если структурированное поле уже содержит конкретные данные, отсутствие их повторения в тексте НЕ является проблемой.
3. Отмечай только реальные проблемы трёх типов:
   - "omission" (пропуск): поле пустое или равно 0; цитату ("quote") оставь пустой строкой "".
   - "ambiguity" (неоднозначность): расплывчатые формулировки без конкретики (например, не указаны смены/часы или условия отложены до собеседования); в "quote" укажи ТОЧНУЮ цитату из JSON текущей вакансии.
   - "contradiction" (противоречие): разные поля противоречат друг другу; в "quote" приведи ОБА исходных значения из JSON текущей вакансии.
4. НЕ выдумывай факты, НЕ цитируй фразы, которых нет в JSON текущей вакансии, и НЕ делай выводов о нарушении закона (ТК РФ и т.д.).
5. НЕ придирайся к мелочам: если в вакансии уже указаны конкретная должность, понятные обязанности, вилка/оклад, конкретный график (например, «пн–пт, 09:00–18:00» или «2/2, 08:00–20:00») и адрес с улицей — НЕ выдумывай искусственные замечания. Если «образование» указано как «Не указано», но требования по навыкам понятны, это НЕ пропуск.
6. Если вакансия описана ясно и без противоречий (особенно если базовые правила вернули пустой список и скрытых противоречий нет), верни пустой массив "issues": [].
7. Учитывай уже найденные правилами замечания — дополни их, только если заметишь реально упущенную неоднозначность, пропуск или противоречие, мешающие соискателю понять условия.

Верни СТРОГО валидный JSON-объект вида:
{
  "issues": [
    {
      "topic": "одна из 7 тем",
      "issue_type": "omission | ambiguity | contradiction",
      "source_field": "имя поля или полей источника",
      "quote": "цитата/значение из поля (пусто для omission; оба значения для contradiction)",
      "problem": "короткое понятное описание сути проблемы",
      "recommendation": "конкретный вопрос или рекомендация для работодателя"
    }
  ]
}"""


def _build_ai_user_prompt(vacancy: VacancySummary, rule_issues: list[Issue]) -> str:
    compact_vacancy = {
        "id": vacancy.vacancy_id,
        "job-name": vacancy.job_name,
        "company": vacancy.company_name,
        "salary_min": vacancy.salary_min,
        "salary_max": vacancy.salary_max,
        "currency": vacancy.currency,
        "employment": vacancy.employment,
        "schedule": vacancy.schedule,
        "duty": vacancy.duty,
        "requirement": {
            "education": vacancy.education,
            "experience": vacancy.experience,
            "qualification": vacancy.qualification,
        },
        "requirements": vacancy.requirements,
        "addresses": vacancy.addresses,
    }
    return (
        "Исходные данные вакансии (API «Работа в России»):\n"
        f"{json.dumps(compact_vacancy, ensure_ascii=False, indent=2)}\n\n"
        "Замечания, уже выявленные базовыми правилами:\n"
        f"{json.dumps([i.to_dict() for i in rule_issues], ensure_ascii=False, indent=2)}\n\n"
        "Проанализируй вакансию. Если базовые правила пропустили неоднозначность или противоречие, добавь их. "
        "Если проблем нет, верни {\"issues\": []}."
    )


_FIELD_LABEL_TOKENS = {
    "job", "name", "duty", "requirements", "requirement", "qualification",
    "education", "experience", "schedule", "employment", "salary", "min",
    "max", "currency", "addresses", "address", "location", "rub",
}


def _vacancy_haystack(vacancy: VacancySummary) -> str:
    parts = [
        vacancy.job_name,
        vacancy.company_name,
        vacancy.duty,
        vacancy.requirements,
        vacancy.qualification,
        vacancy.education,
        vacancy.schedule,
        vacancy.employment,
        " ".join(vacancy.addresses),
        str(vacancy.salary_min or ""),
        str(vacancy.salary_max or ""),
        str(vacancy.experience if vacancy.experience is not None else ""),
    ]
    return " ".join(parts).lower()


def _is_quote_grounded(quote: str, haystack: str) -> bool:
    """Проверяет, что цитата ИИ действительно опирается на текст текущей вакансии."""
    q = quote.strip().lower()
    if not q:
        return False
    if q in haystack:
        return True
    tokens = [
        tok
        for tok in re.findall(r"[а-яёa-z0-9]{3,}", q)
        if tok not in _FIELD_LABEL_TOKENS
    ]
    if not tokens:
        return False
    matched = sum(1 for tok in tokens if tok in haystack)
    return (matched / len(tokens)) >= 0.6


def _is_false_omission(topic: str, vacancy: VacancySummary) -> bool:
    """Отсекает ложные пропуски по уже заполненным структурированным полям."""
    if topic == "название должности":
        return bool(vacancy.job_name)
    if topic == "обязанности":
        return bool(vacancy.duty)
    if topic == "оплата":
        return (vacancy.salary_min or 0) > 0 or (vacancy.salary_max or 0) > 0
    if topic == "график":
        return bool(vacancy.schedule)
    if topic == "тип занятости":
        return bool(vacancy.employment)
    if topic == "требования":
        return bool(vacancy.requirements or vacancy.qualification or (vacancy.experience or 0) > 0)
    return False


def _sanitize_ai_issues(payload: dict[str, Any], vacancy: VacancySummary | None = None) -> list[Issue]:
    raw_issues = payload.get("issues")
    if not isinstance(raw_issues, list):
        return []

    haystack = _vacancy_haystack(vacancy) if vacancy is not None else ""
    sanitized: list[Issue] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip().lower()
        if topic not in VALID_TOPICS:
            continue
        issue_type = str(item.get("issue_type") or "").strip().lower()
        if issue_type not in VALID_ISSUE_TYPES:
            issue_type = "ambiguity"
        source_field = str(item.get("source_field") or "").strip() or "description"
        quote = "" if issue_type == "omission" else str(item.get("quote") or "").strip()
        problem = str(item.get("problem") or "").strip()
        recommendation = str(item.get("recommendation") or "").strip()

        # Страховка от юридических выводов (требование задания)
        lowered_all = f"{problem} {recommendation}".lower()
        if "нарушени" in lowered_all and ("закон" in lowered_all or "тк рф" in lowered_all):
            continue
        if not problem or not recommendation:
            continue

        # Страховка от галлюцинаций ИИ (вымышленные цитаты и ложные пропуски)
        if vacancy is not None:
            if issue_type == "omission" and _is_false_omission(topic, vacancy):
                continue
            if issue_type in ("ambiguity", "contradiction") and not _is_quote_grounded(quote, haystack):
                continue
            # Если в описании проблемы модель взяла в «кавычки» фразу, которой нет в вакансии — отсекаем
            quoted_in_problem = re.findall(r"«([^»]{4,})»", problem)
            if any(not _is_quote_grounded(phrase, haystack) for phrase in quoted_in_problem):
                continue

        sanitized.append(
            Issue(
                topic=topic,
                issue_type=issue_type,
                source_field=source_field,
                quote=quote,
                problem=problem,
                recommendation=recommendation,
                detected_by="ai",
            )
        )
    return sanitized


def _merge_issues(rule_issues: list[Issue], ai_issues: list[Issue]) -> list[Issue]:
    """Объединяет замечания правил и ИИ без дубликатов по теме и типу."""
    merged: list[Issue] = list(rule_issues)
    existing_keys = {(i.topic, i.issue_type) for i in rule_issues}
    existing_topics = {i.topic for i in rule_issues}

    for ai_issue in ai_issues:
        key = (ai_issue.topic, ai_issue.issue_type)
        if key in existing_keys:
            # Усиливаем пометку, что замечание подтверждено и правилами, и ИИ
            for existing in merged:
                if (existing.topic, existing.issue_type) == key:
                    existing.detected_by = "hybrid"
                    break
            continue
        # Не добавляем дублирующий ambiguity, если по той же теме уже есть contradiction или omission
        if ai_issue.issue_type == "ambiguity" and ai_issue.topic in existing_topics:
            continue
        merged.append(ai_issue)
        existing_keys.add(key)
        existing_topics.add(ai_issue.topic)

    return merged


def analyze_vacancies(
    raw_vacancies: list[dict[str, Any]],
    config: AppConfig,
    mode: str,
    source: str,
    pages_fetched: int = 0,
    provider_override: str | None = None,
    llm_client: BaseLLMClient | None = None,
    strict_ai: bool = False,
) -> AnalysisReport:
    """
    Выполняет анализ списка вакансий (гибрид: правила + ИИ).
    Гарантирует идемпотентность: один итоговый объект на уникальный ID вакансии.
    """
    provider = (provider_override or config.llm_provider).strip().lower()
    ai_applied = False
    ai_model: str | None = None
    ai_note = ""

    client: BaseLLMClient | None = llm_client
    if client is None and provider != "rules":
        try:
            client = create_llm_client(config, provider_override=provider)
        except LLMClientError as exc:
            if strict_ai:
                raise
            ai_note = f"ИИ ({provider}) не настроен: {exc} Использованы базовые правила."
            client = None

    if client is not None:
        ai_model = client.model_name
        provider = client.provider_name
    elif provider == "rules":
        ai_note = "Режим только базовых правил (LLM_PROVIDER=rules)."

    # Дедупликация по ID вакансии (повторный запуск / дубликаты в выборке -> 1 результат на ID)
    deduped_by_id: dict[str, VacancySummary] = {}
    ordered_ids: list[str] = []
    for raw in raw_vacancies:
        summary = normalize_vacancy(raw)
        if summary.vacancy_id not in deduped_by_id:
            ordered_ids.append(summary.vacancy_id)
        deduped_by_id[summary.vacancy_id] = summary

    report_items: list[VacancyReportItem] = []
    ai_failures = 0
    ai_successes = 0

    for vid in ordered_ids:
        vacancy = deduped_by_id[vid]
        rule_issues = run_rule_checks(vacancy)
        ai_issues: list[Issue] = []

        if client is not None:
            try:
                ai_response = client.chat_json(
                    system_prompt=AI_SYSTEM_PROMPT,
                    user_prompt=_build_ai_user_prompt(vacancy, rule_issues),
                    temperature=0.1,
                )
                ai_issues = _sanitize_ai_issues(ai_response, vacancy=vacancy)
                ai_successes += 1
            except LLMClientError as exc:
                ai_failures += 1
                if strict_ai:
                    raise
                if not ai_note:
                    ai_note = f"ИИ ({provider}) недоступен во время обработки: {exc} Сохранены результаты базовых правил."
                # Прекращаем повторные таймауты, если локальный сервер Ollama выключен
                if ai_failures >= 1 and provider == "ollama":
                    client = None

        final_issues = _merge_issues(rule_issues, ai_issues)
        report_items.append(
            VacancyReportItem(
                vacancy_id=vacancy.vacancy_id,
                vacancy_url=vacancy.vacancy_url,
                job_name=vacancy.job_name,
                company_name=vacancy.company_name,
                issues=final_issues,
            )
        )

    if ai_successes > 0:
        ai_applied = True
        ai_note = (
            f"ИИ-анализ выполнен ({provider}, модель {ai_model}): обработано {ai_successes} из {len(ordered_ids)} вакансий."
        )

    vacancies_with_issues = sum(1 for item in report_items if item.issues)
    total_issues = sum(len(item.issues) for item in report_items)

    return AnalysisReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        mode=mode,
        source=source,
        ai_provider=provider,
        ai_model=ai_model,
        ai_applied=ai_applied,
        ai_note=ai_note,
        pages_fetched=pages_fetched,
        total_vacancies=len(report_items),
        vacancies_with_issues=vacancies_with_issues,
        total_issues=total_issues,
        vacancies=report_items,
    )


def save_report_atomic(report: AnalysisReport, output_path: str | Path) -> Path:
    """Атомарно сохраняет отчёт в JSON, чтобы не повредить предыдущий файл при сбое."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    content = json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(target)
    return target


def run_verification_mode(
    input_path: str | Path,
    output_path: str | Path,
    config: AppConfig,
    provider_override: str | None = None,
    llm_client: BaseLLMClient | None = None,
    strict_ai: bool = False,
) -> AnalysisReport:
    """Проверочный режим: читает локальный JSON без обращений к порталу и сохраняет отчёт."""
    raw_vacancies = load_vacancies_from_file(input_path)
    report = analyze_vacancies(
        raw_vacancies=raw_vacancies,
        config=config,
        mode="verification",
        source=str(input_path),
        pages_fetched=0,
        provider_override=provider_override,
        llm_client=llm_client,
        strict_ai=strict_ai,
    )
    save_report_atomic(report, output_path)
    return report


def run_working_mode(
    config: AppConfig,
    output_path: str | Path | None = None,
    api_url: str | None = None,
    max_vacancies: int | None = None,
    page_size: int | None = None,
    provider_override: str | None = None,
    llm_client: BaseLLMClient | None = None,
    http_get: Any = None,
    allow_custom_hosts: bool = False,
) -> dict[str, Any]:
    """
    Рабочий режим: загружает вакансии с API региона 39 (минимум 2 страницы),
    анализирует их и сохраняет отчёт.
    При недоступности API сообщает об ошибке и СОХРАНЯЕТ последний успешный отчёт, если он есть.
    """
    target_path = Path(output_path or config.last_report_path)
    source_url = api_url or config.api_url
    limit = max_vacancies if max_vacancies is not None else config.max_vacancies
    per_page = page_size if page_size is not None else config.page_size

    try:
        raw_vacancies, pages_fetched = fetch_vacancies_paginated(
            api_url=source_url,
            max_vacancies=limit,
            page_size=per_page,
            timeout=config.http_timeout_seconds,
            http_get=http_get,
            allow_custom_hosts=allow_custom_hosts,
        )
    except TrudvsemAPIError as exc:
        has_previous = target_path.is_file()
        message = (
            f"Ошибка загрузки API «Работа в России»: {exc}. "
            + (
                f"Последний успешный отчёт сохранён без изменений: {target_path}"
                if has_previous
                else "Предыдущий успешный отчёт отсутствует."
            )
        )
        print(f"[ERROR] {message}", file=sys.stderr)
        previous_report = None
        if has_previous:
            try:
                previous_report = json.loads(target_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                previous_report = None
        return {
            "status": "error",
            "error": str(exc),
            "message": message,
            "preserved_last_report": has_previous,
            "report_path": str(target_path) if has_previous else None,
            "report": previous_report,
        }

    report = analyze_vacancies(
        raw_vacancies=raw_vacancies,
        config=config,
        mode="working",
        source=source_url,
        pages_fetched=pages_fetched,
        provider_override=provider_override,
        llm_client=llm_client,
    )
    saved_path = save_report_atomic(report, target_path)
    return {
        "status": "ok",
        "message": (
            f"Успешно обработано {report.total_vacancies} вакансий "
            f"({pages_fetched} стр.), найдено замечаний: {report.total_issues}."
        ),
        "preserved_last_report": False,
        "report_path": str(saved_path),
        "report": report.to_dict(),
    }
