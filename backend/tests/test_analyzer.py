"""Автотесты анализатора, API-клиента, идемпотентности, отказоустойчивости и доп. сценария."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from backend.analyzer import analyze_vacancies, run_verification_mode, run_working_mode
from backend.config import AppConfig
from backend.llm_clients import BaseLLMClient
from backend.resume_tailor import generate_resume_draft
from backend.trudvsem_client import (
    TrudvsemAPIError,
    fetch_vacancies_paginated,
    load_vacancies_from_file,
    validate_source_url,
)


DEMO_JSON_PATH = Path("sample_data/demo_vacancies.json")
SAMPLE_RESUMES_PATH = Path("sample_data/sample_resumes.json")


class StubLLMClient(BaseLLMClient):
    """Тестовый ИИ-клиент для проверки интеграции шага ИИ без сетевых вызовов."""

    provider_name = "ollama"
    model_name = "stub-qwen2.5"

    def __init__(self, response_map: dict[str, dict[str, Any]] | None = None) -> None:
        self.calls = 0
        self.response_map = response_map or {}

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict[str, Any]:
        self.calls += 1
        for key, payload in self.response_map.items():
            if key in user_prompt:
                return payload
        return {"issues": []}


class VacancyAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = AppConfig(llm_provider="rules")

    def test_official_demo_dataset_precision(self) -> None:
        """Проверяет все 10 учебных вакансий организаторов КАНТКОД."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "report.json"
            report = run_verification_mode(
                input_path=DEMO_JSON_PATH,
                output_path=out_file,
                config=self.config,
            )
            self.assertTrue(out_file.is_file())
            self.assertEqual(report.total_vacancies, 10)

            by_id = {item.vacancy_id: item for item in report.vacancies}

            # 4 чистые эталонные вакансии должны иметь пустой массив замечаний []
            for clean_id in ("DEMO-39-001", "DEMO-39-005", "DEMO-39-007", "DEMO-39-009"):
                self.assertEqual(
                    by_id[clean_id].issues,
                    [],
                    msg=f"Ожидалось 0 замечаний для {clean_id}, получено: {by_id[clean_id].issues}",
                )

            # DEMO-39-002: пропуск оплаты (пустая цитата), гибкий график, размытые обязанности/требования
            issues_002 = by_id["DEMO-39-002"].issues
            salary_002 = [i for i in issues_002 if i.topic == "оплата"]
            self.assertEqual(len(salary_002), 1)
            self.assertEqual(salary_002[0].issue_type, "omission")
            self.assertEqual(salary_002[0].quote, "")
            self.assertTrue(any(i.topic == "график" and i.issue_type == "ambiguity" for i in issues_002))
            self.assertTrue(any(i.topic == "обязанности" for i in issues_002))

            # DEMO-39-003: противоречие по опыту (0 vs 5 лет) с обоими значениями в quote
            issues_003 = by_id["DEMO-39-003"].issues
            exp_003 = [i for i in issues_003 if i.topic == "требования" and i.issue_type == "contradiction"]
            self.assertEqual(len(exp_003), 1)
            self.assertIn("0", exp_003[0].quote)
            self.assertIn("5 лет", exp_003[0].quote)

            # DEMO-39-004: противоречие дистанционной работы и ежедневного офиса
            issues_004 = by_id["DEMO-39-004"].issues
            wp_004 = [i for i in issues_004 if i.topic == "место работы" and i.issue_type == "contradiction"]
            self.assertEqual(len(wp_004), 1)
            self.assertIn("дистанционная", wp_004[0].quote.lower())
            self.assertIn("офисе", wp_004[0].quote.lower())

            # DEMO-39-006: общее название, неполная зарплата, сменный график, общие обязанности, собеседование, регион
            issues_006 = by_id["DEMO-39-006"].issues
            topics_006 = {i.topic for i in issues_006}
            self.assertTrue({"название должности", "оплата", "график", "обязанности", "место работы"}.issubset(topics_006))

            # DEMO-39-008: противоречие графика (Гибкий график vs Пятидневная рабочая неделя 09:00-18:00)
            issues_008 = by_id["DEMO-39-008"].issues
            sched_008 = [i for i in issues_008 if i.topic == "график" and i.issue_type == "contradiction"]
            self.assertEqual(len(sched_008), 1)
            self.assertIn("Гибкий график", sched_008[0].quote)
            self.assertIn("09:00", sched_008[0].quote)

            # DEMO-39-010: противоречие опыта (0 vs опыт разработки) + формат/адрес на собеседовании
            issues_010 = by_id["DEMO-39-010"].issues
            self.assertTrue(any(i.topic == "требования" and i.issue_type == "contradiction" for i in issues_010))
            self.assertTrue(any(i.topic == "место работы" for i in issues_010))

    def test_idempotency_deduplicates_vacancy_ids(self) -> None:
        """Повторный запуск / дубликаты ID сохраняют один результат на ID вакансии."""
        vacancies = load_vacancies_from_file(DEMO_JSON_PATH)
        duplicated = vacancies + vacancies[:3]
        report = analyze_vacancies(
            raw_vacancies=duplicated,
            config=self.config,
            mode="verification",
            source="test-dup",
        )
        self.assertEqual(report.total_vacancies, 10)
        ids = [item.vacancy_id for item in report.vacancies]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ai_step_enriches_report_and_blocks_legal_claims(self) -> None:
        """Проверяет участие ИИ в формировании отчёта и фильтрацию выводов о нарушении закона."""
        vacancies = load_vacancies_from_file(DEMO_JSON_PATH)[:2]
        stub = StubLLMClient(
            response_map={
                "DEMO-39-002": {
                    "issues": [
                        {
                            "topic": "тип занятости",
                            "issue_type": "ambiguity",
                            "source_field": "employment",
                            "quote": "Частичная занятость",
                            "problem": "Не указана доля ставки или количество часов в неделю.",
                            "recommendation": "Уточните долю ставки (например, 0,5 ставки или 20 часов в неделю).",
                        },
                        {
                            "topic": "оплата",
                            "issue_type": "ambiguity",
                            "source_field": "salary_min",
                            "quote": "0",
                            "problem": "Это прямое нарушение закона ТК РФ.",
                            "recommendation": "Исправьте нарушение закона.",
                        },
                    ]
                }
            }
        )
        report = analyze_vacancies(
            raw_vacancies=vacancies,
            config=AppConfig(llm_provider="ollama"),
            mode="verification",
            source="test-ai",
            llm_client=stub,
        )
        self.assertTrue(report.ai_applied)
        self.assertEqual(stub.calls, 2)
        by_id = {item.vacancy_id: item for item in report.vacancies}
        emp_issues = [i for i in by_id["DEMO-39-002"].issues if i.topic == "тип занятости"]
        self.assertEqual(len(emp_issues), 1)
        self.assertEqual(emp_issues[0].detected_by, "ai")
        # Утверждения о нарушении ТК РФ должны быть отфильтрованы
        self.assertFalse(any("тк рф" in i.problem.lower() for i in by_id["DEMO-39-002"].issues))

    def test_pagination_fetches_at_least_two_pages(self) -> None:
        """Проверяет постраничную загрузку (минимум 2 страницы при достаточном лимите)."""
        all_vacancies = load_vacancies_from_file(DEMO_JSON_PATH)
        requested_urls: list[str] = []

        def fake_http_get(url: str, timeout: int) -> dict[str, Any]:
            requested_urls.append(url)
            if "offset=0" in url:
                chunk = all_vacancies[:4]
            else:
                chunk = all_vacancies[4:8]
            return {
                "status": "200",
                "meta": {"total": str(len(all_vacancies)), "limit": "4", "offset": "0"},
                "results": {"vacancies": [{"vacancy": v} for v in chunk]},
            }

        items, pages = fetch_vacancies_paginated(
            api_url="http://opendata.trudvsem.ru/api/v1/vacancies/region/39",
            max_vacancies=8,
            page_size=4,
            http_get=fake_http_get,
        )
        self.assertEqual(pages, 2)
        self.assertEqual(len(items), 8)
        self.assertEqual(len(requested_urls), 2)

    def test_working_mode_preserves_last_report_on_api_error(self) -> None:
        """При недоступности API сервис возвращает ошибку и НЕ затирает последний успешный отчёт."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "latest_report.json"
            sentinel = {"meta": {"source": "previous-ok"}, "vacancies": [{"vacancy_id": "OLD-1", "issues": []}]}
            report_path.write_text(json.dumps(sentinel, ensure_ascii=False), encoding="utf-8")

            def failing_http_get(url: str, timeout: int) -> dict[str, Any]:
                raise TrudvsemAPIError("Connection timed out")

            result = run_working_mode(
                config=self.config,
                output_path=report_path,
                http_get=failing_http_get,
            )
            self.assertEqual(result["status"], "error")
            self.assertTrue(result["preserved_last_report"])
            still_on_disk = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(still_on_disk["vacancies"][0]["vacancy_id"], "OLD-1")

    def test_url_validation_blocks_ssrf_targets(self) -> None:
        """Проверяет блокировку небезопасных URL и приватных адресов."""
        self.assertTrue(
            validate_source_url("http://opendata.trudvsem.ru/api/v1/vacancies/region/39").startswith("http://")
        )
        for bad_url in (
            "file:///etc/passwd",
            "http://127.0.0.1:8080/secret",
            "http://localhost/admin",
            "http://169.254.169.254/latest/meta-data/",
            "https://evil.example.com/api",
        ):
            with self.assertRaises(TrudvsemAPIError):
                validate_source_url(bad_url)

    def test_bonus_resume_tailor_uses_only_source_facts(self) -> None:
        """Проверяет доп. сценарий: навыки берутся строго из исходного резюме."""
        vacancies = load_vacancies_from_file(DEMO_JSON_PATH)
        candidates = json.loads(SAMPLE_RESUMES_PATH.read_text(encoding="utf-8"))["candidates"]

        # Даже если ИИ пытается выдумать лишний навык, фильтр оставляет только исходные
        stub = StubLLMClient(
            response_map={
                "DEMO-39-001": {
                    "summary": "Подготовленный черновик под документооборот.",
                    "matched_skills": ["Ведение электронного архива", "Выдуманный навык Kubernetes"],
                    "honest_gaps_and_questions": ["Уточните используемую СЭД."],
                }
            }
        )
        draft = generate_resume_draft(
            raw_vacancy=vacancies[0],
            candidate=candidates[0],
            config=AppConfig(llm_provider="ollama"),
            llm_client=stub,
        )
        self.assertTrue(draft.ai_used)
        self.assertIn("Ведение электронного архива", draft.matched_skills)
        self.assertNotIn("Выдуманный навык Kubernetes", draft.matched_skills)
        self.assertIn("DEMO-39-001", draft.draft_markdown)


if __name__ == "__main__":
    unittest.main()
