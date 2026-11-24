"""Дополнительный сценарий: подготовка черновика резюме под выбранную вакансию региона 39."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.config import AppConfig
from backend.llm_clients import BaseLLMClient, LLMClientError, create_llm_client
from backend.models import ResumeDraftResult, VacancySummary
from backend.rules import normalize_vacancy


RESUME_SYSTEM_PROMPT = """Ты — карьерный консультант портала «Работа в России» (Калининградская область).
Подготовь черновик резюме соискателя, адаптированный под выбранную вакансию, на основе исходного резюме.

СТРОГИЕ ПРАВИЛА:
1. Бери опыт, навыки, достижения и образование ИСКЛЮЧИТЕЛЬНО из исходного резюме соискателя.
2. Запрещено придумывать несуществующие места работы, курсы, инструменты или годы стажа.
3. Сделай акцент на тех навыках и задачах соискателя, которые релевантны выбранной вакансии.
4. Если в вакансии есть требования, которых нет в резюме, честно перечисли их в "honest_gaps_and_questions".

Верни СТРОГО валидный JSON-объект:
{
  "summary": "краткое сопроводительное резюме (2-3 предложения строго по фактам из исходного резюме)",
  "matched_skills": ["навыки из резюме, подходящие под вакансию"],
  "honest_gaps_and_questions": ["что стоит уточнить у работодателя или подтянуть соискателю"]
}"""


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[а-яёa-z0-9]{3,}", text.lower())
    # Простая нормализация окончаний для русского языка
    return {w[:5] if len(w) > 5 else w for w in words}


def _match_skills_deterministic(vacancy: VacancySummary, candidate: dict[str, Any]) -> list[str]:
    vacancy_text = " ".join(
        [
            vacancy.job_name,
            vacancy.duty,
            vacancy.requirements,
            vacancy.qualification,
            vacancy.education,
        ]
    )
    vac_tokens = _tokenize(vacancy_text)
    skills = candidate.get("skills") if isinstance(candidate.get("skills"), list) else []

    matched: list[str] = []
    secondary: list[str] = []
    for skill in skills:
        skill_str = str(skill).strip()
        if not skill_str:
            continue
        skill_tokens = _tokenize(skill_str)
        if skill_tokens & vac_tokens:
            matched.append(skill_str)
        else:
            secondary.append(skill_str)

    return matched if matched else secondary[:4]


def _detect_honest_gaps(vacancy: VacancySummary, candidate: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    cand_years = int(candidate.get("experience_years") or 0)
    if vacancy.experience is not None and vacancy.experience > cand_years:
        gaps.append(
            f"В вакансии указан опыт от {vacancy.experience} лет, в исходном резюме — {cand_years} год(а). Уточните готовность работодателя к кандидатам с меньшим стажем."
        )
    if vacancy.education and vacancy.education.lower() != "не указано":
        cand_edu = str(candidate.get("education") or "").lower()
        if vacancy.education.lower() not in cand_edu and "высш" in vacancy.education.lower() and "высш" not in cand_edu:
            gaps.append(
                f"Вакансия указывает образование «{vacancy.education}» — уточните, подойдёт ли ваш уровень образования из резюме."
            )
    if not vacancy.salary_min and not vacancy.salary_max:
        gaps.append("В вакансии не указан размер оплаты — уточните оклад и систему премирования на этапе отклика.")
    if "гибк" in vacancy.schedule.lower() or "уточня" in vacancy.qualification.lower():
        gaps.append("График или формат работы описаны не полностью — уточните рабочие часы и адрес перед собеседованием.")
    if not gaps:
        gaps.append("Ключевые требования вакансии покрыты исходным резюме; перед отправкой проверьте актуальность контактов.")
    return gaps


def _render_markdown(
    candidate_name: str,
    vacancy: VacancySummary,
    summary: str,
    matched_skills: list[str],
    experience: list[dict[str, Any]],
    education: str,
    gaps: list[str],
) -> str:
    lines = [
        f"# Черновик резюме под вакансию «{vacancy.job_name}»",
        f"**Кандидат:** {candidate_name}",
        f"**Работодатель (регион 39):** {vacancy.company_name or 'Не указан'} (`{vacancy.vacancy_id}`)",
        "",
        "## О себе",
        summary,
        "",
        "## Релевантные навыки (из исходного резюме)",
    ]
    for skill in matched_skills:
        lines.append(f"- {skill}")

    lines.append("")
    lines.append("## Опыт работы (без изменений фактов)")
    for exp in experience:
        role = exp.get("role", "")
        org = exp.get("organization", "")
        period = exp.get("period", "")
        lines.append(f"- **{role}** — {org} ({period})")
        for ach in exp.get("achievements", []):
            lines.append(f"  - {ach}")

    lines.extend(
        [
            "",
            "## Образование",
            education or "Не указано в исходном резюме",
            "",
            "## На что обратить внимание при отклике",
        ]
    )
    for gap in gaps:
        lines.append(f"- {gap}")

    return "\n".join(lines)


def generate_resume_draft(
    raw_vacancy: dict[str, Any],
    candidate: dict[str, Any],
    config: AppConfig,
    provider_override: str | None = None,
    llm_client: BaseLLMClient | None = None,
) -> ResumeDraftResult:
    """Формирует черновик резюме под вакансию, строго опираясь на исходные факты соискателя."""
    vacancy = normalize_vacancy(raw_vacancy)
    candidate_id = str(candidate.get("id") or "CUSTOM-RESUME")
    candidate_name = str(candidate.get("full_name") or "Соискатель (обезличенный профиль)")
    education = str(candidate.get("education") or "")
    experience = candidate.get("experience") if isinstance(candidate.get("experience"), list) else []
    source_skills = [str(s).strip() for s in (candidate.get("skills") or []) if str(s).strip()]

    matched_skills = _match_skills_deterministic(vacancy, candidate)
    gaps = _detect_honest_gaps(vacancy, candidate)
    base_summary = str(candidate.get("summary") or "").strip()
    if not base_summary:
        base_summary = (
            f"Кандидат на позицию «{vacancy.job_name}» с подтверждёнными навыками: "
            f"{', '.join(matched_skills[:4])}."
        )

    provider = (provider_override or config.llm_provider).strip().lower()
    ai_used = False
    client = llm_client
    if client is None and provider != "rules":
        try:
            client = create_llm_client(config, provider_override=provider)
        except LLMClientError:
            client = None

    summary = base_summary
    if client is not None:
        user_prompt = (
            f"Вакансия:\n{json.dumps({'id': vacancy.vacancy_id, 'job-name': vacancy.job_name, 'duty': vacancy.duty, 'requirements': vacancy.requirements, 'qualification': vacancy.qualification, 'education': vacancy.education, 'experience': vacancy.experience}, ensure_ascii=False, indent=2)}\n\n"
            f"Исходное резюме соискателя:\n{json.dumps(candidate, ensure_ascii=False, indent=2)}"
        )
        try:
            ai_data = client.chat_json(RESUME_SYSTEM_PROMPT, user_prompt, temperature=0.2)
            ai_summary = str(ai_data.get("summary") or "").strip()
            if ai_summary:
                summary = ai_summary
            # Фильтруем навыки строго по белому списку навыков из исходного резюме (защита от выдумок!)
            source_lower_map = {s.lower(): s for s in source_skills}
            raw_ai_skills = ai_data.get("matched_skills")
            if isinstance(raw_ai_skills, list):
                verified_skills = [
                    source_lower_map[str(s).strip().lower()]
                    for s in raw_ai_skills
                    if str(s).strip().lower() in source_lower_map
                ]
                if verified_skills:
                    matched_skills = list(dict.fromkeys(verified_skills))
            raw_ai_gaps = ai_data.get("honest_gaps_and_questions")
            if isinstance(raw_ai_gaps, list):
                clean_gaps = [str(g).strip() for g in raw_ai_gaps if str(g).strip()]
                if clean_gaps:
                    gaps = clean_gaps
            ai_used = True
            provider = client.provider_name
        except LLMClientError:
            ai_used = False

    draft_md = _render_markdown(
        candidate_name=candidate_name,
        vacancy=vacancy,
        summary=summary,
        matched_skills=matched_skills,
        experience=experience,
        education=education,
        gaps=gaps,
    )

    return ResumeDraftResult(
        vacancy_id=vacancy.vacancy_id,
        vacancy_title=vacancy.job_name,
        company_name=vacancy.company_name,
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        ai_provider=provider,
        ai_used=ai_used,
        summary=summary,
        matched_skills=matched_skills,
        highlighted_experience=experience,
        education=education,
        honest_gaps_and_questions=gaps,
        draft_markdown=draft_md,
    )
