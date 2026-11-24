"""Типизированные модели данных для вакансий, замечаний, отчёта и доп. сценария."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


VALID_TOPICS = (
    "название должности",
    "обязанности",
    "требования",
    "оплата",
    "график",
    "место работы",
    "тип занятости",
)

VALID_ISSUE_TYPES = ("omission", "ambiguity", "contradiction")


@dataclass
class Issue:
    """Одно замечание по качеству описания вакансии."""

    topic: str
    issue_type: str  # omission | ambiguity | contradiction
    source_field: str
    quote: str
    problem: str
    recommendation: str
    detected_by: str = "rules"  # rules | ai | hybrid

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "issue_type": self.issue_type,
            "source_field": self.source_field,
            "quote": self.quote,
            "problem": self.problem,
            "recommendation": self.recommendation,
            "detected_by": self.detected_by,
        }


@dataclass
class VacancySummary:
    """Нормализованная сводка исходной вакансии из API «Работа в России»."""

    vacancy_id: str
    vacancy_url: str | None
    job_name: str
    company_name: str
    salary_min: int | None
    salary_max: int | None
    currency: str
    employment: str
    schedule: str
    duty: str
    education: str
    experience: int | None
    qualification: str
    requirements: str
    addresses: list[str]
    creation_date: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class VacancyReportItem:
    """Результат проверки одной вакансии в итоговом JSON-отчёте."""

    vacancy_id: str
    vacancy_url: str | None
    job_name: str
    company_name: str
    issues: list[Issue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vacancy_id": self.vacancy_id,
            "vacancy_url": self.vacancy_url,
            "job_name": self.job_name,
            "company_name": self.company_name,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class AnalysisReport:
    """Корневая структура JSON-отчёта."""

    generated_at: str
    mode: str  # "verification" | "working"
    source: str
    ai_provider: str
    ai_model: str | None
    ai_applied: bool
    ai_note: str
    pages_fetched: int
    total_vacancies: int
    vacancies_with_issues: int
    total_issues: int
    vacancies: list[VacancyReportItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "generated_at": self.generated_at,
                "mode": self.mode,
                "source": self.source,
                "ai_provider": self.ai_provider,
                "ai_model": self.ai_model,
                "ai_applied": self.ai_applied,
                "ai_note": self.ai_note,
                "pages_fetched": self.pages_fetched,
                "total_vacancies": self.total_vacancies,
                "vacancies_with_issues": self.vacancies_with_issues,
                "total_issues": self.total_issues,
            },
            "vacancies": [item.to_dict() for item in self.vacancies],
        }


@dataclass
class ResumeDraftResult:
    """Результат дополнительного сценария — черновик резюме под выбранную вакансию."""

    vacancy_id: str
    vacancy_title: str
    company_name: str
    candidate_id: str
    candidate_name: str
    ai_provider: str
    ai_used: bool
    summary: str
    matched_skills: list[str]
    highlighted_experience: list[dict[str, Any]]
    education: str
    honest_gaps_and_questions: list[str]
    draft_markdown: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
