"""Детерминированные правила проверки вакансий «Работа в России» (7 критериев)."""

from __future__ import annotations

import re
from typing import Any

from backend.models import Issue, VacancySummary


GENERIC_TITLES = {
    "специалист",
    "сотрудник",
    "работник",
    "менеджер",
    "помощник",
    "ассистент",
    "стажер",
    "стажёр",
    "мастер",
    "инженер",
    "оператор",
}

VAGUE_DUTY_PATTERNS = (
    r"различн\w*\s+поручен",
    r"други\w*\s+задач\w*\s+по\s+необходимост",
    r"проч\w*\s+поручен",
    r"выполнен\w*\s+поручен\w*\s+руковод",
    r"обязанност\w*\s+обсужда\w*\s+на\s+собеседован",
)

HIDDEN_CONDITIONS_PATTERNS = (
    r"обсужда\w*\s+на\s+собеседован",
    r"уточня\w*\s+(?:при|на)\s+собеседован",
    r"подробност\w*\s+(?:по\s+телефону|на\s+собеседован)",
)

SOFT_SKILLS_ONLY_WORDS = {
    "ответственность",
    "активность",
    "стрессоустойчивость",
    "коммуникабельность",
    "пунктуальность",
    "исполнительность",
    "внимательность",
    "желание",
    "работать",
    "обучаемость",
    "дисциплинированность",
    "инициативность",
    "энергичность",
    "доброжелательность",
    "аккуратность",
    "честность",
}

TIME_RANGE_RE = re.compile(
    r"(?:\b\d{1,2}[:.]\d{2}\s*[–—\-]\s*\d{1,2}[:.]\d{2}\b|\bс\s*\d{1,2}[:.]\d{2}\s*до\s*\d{1,2}[:.]\d{2}\b)",
    re.IGNORECASE,
)
SHIFT_PATTERN_RE = re.compile(r"\b\d\s*/\s*\d\b")
WEEKDAYS_RE = re.compile(
    r"(?:понедельник|вторник|пятиднев\w*|5\s*/\s*2|пн\s*[–—\-]\s*пт|будн\w*)",
    re.IGNORECASE,
)
STREET_DETAIL_RE = re.compile(
    r"(?:\bул\.|\bулица\b|\bпр\.|\bпр-кт\b|\bпроспект\b|\bпер\.|\bпереулок\b|\bнаб\.|\bпл\.|\bд\.|\bдом\b|\bкорп\.|\bстр\.)",
    re.IGNORECASE,
)
EXPERIENCE_YEARS_RE = re.compile(
    r"(?:не\s+менее|от|минимум|стаж\s+от)\s*(\d+)\s*(?:лет|год|года)",
    re.IGNORECASE,
)
EXPERIENCE_REQUIRED_PHRASE_RE = re.compile(
    r"\bопыт\s+(?:работы\s+|разработки\s+|ведения\s+|управления\s+|проведения\s+)[^\.,;]{3,}",
    re.IGNORECASE,
)
REMOTE_PHRASE_RE = re.compile(
    r"(?:полностью\s+дистанционн\w*|удалённ\w*\s+работ\w*|удаленн\w*\s+работ\w*|дистанционн\w*\s+формат|из\s+любого\s+города)",
    re.IGNORECASE,
)
OFFICE_MANDATORY_RE = re.compile(
    r"(?:обязательн\w*\s+ежедневн\w*\s+присутств\w*\s+в\s+офис|присутств\w*\s+в\s+офис\w*|работа\s+в\s+офисе\s+к\s+\d)",
    re.IGNORECASE,
)


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _to_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_vacancy(raw: dict[str, Any]) -> VacancySummary:
    """Приводит сырой объект вакансии API «Работа в России» к структурированной модели."""
    vacancy_id = _clean_str(raw.get("id")) or "UNKNOWN-ID"
    vacancy_url = _clean_str(raw.get("vac_url") or raw.get("url")) or None

    company = raw.get("company") if isinstance(raw.get("company"), dict) else {}
    company_name = _clean_str(company.get("name"))

    req = raw.get("requirement") if isinstance(raw.get("requirement"), dict) else {}
    education = _clean_str(req.get("education"))
    experience = _to_int_or_none(req.get("experience"))
    qualification = _clean_str(req.get("qualification"))

    addresses_raw = raw.get("addresses")
    addresses: list[str] = []
    if isinstance(addresses_raw, dict):
        addr_list = addresses_raw.get("address")
        if isinstance(addr_list, list):
            for entry in addr_list:
                if isinstance(entry, dict):
                    loc = _clean_str(entry.get("location"))
                    if loc:
                        addresses.append(loc)
                elif isinstance(entry, str) and entry.strip():
                    addresses.append(_clean_str(entry))
        elif isinstance(addr_list, dict):
            loc = _clean_str(addr_list.get("location"))
            if loc:
                addresses.append(loc)
    elif isinstance(addresses_raw, list):
        for entry in addresses_raw:
            if isinstance(entry, dict):
                loc = _clean_str(entry.get("location"))
                if loc:
                    addresses.append(loc)
            elif isinstance(entry, str) and entry.strip():
                addresses.append(_clean_str(entry))

    return VacancySummary(
        vacancy_id=vacancy_id,
        vacancy_url=vacancy_url,
        job_name=_clean_str(raw.get("job-name") or raw.get("job_name")),
        company_name=company_name,
        salary_min=_to_int_or_none(raw.get("salary_min")),
        salary_max=_to_int_or_none(raw.get("salary_max")),
        currency=_clean_str(raw.get("currency")) or "RUB",
        employment=_clean_str(raw.get("employment")),
        schedule=_clean_str(raw.get("schedule")),
        duty=_clean_str(raw.get("duty")),
        education=education,
        experience=experience,
        qualification=qualification,
        requirements=_clean_str(raw.get("requirements")),
        addresses=addresses,
        creation_date=_clean_str(raw.get("creation-date") or raw.get("creation_date")),
        raw=raw,
    )


def _is_soft_skills_only(text: str) -> bool:
    tokens = re.findall(r"[а-яёa-z]+", text.lower())
    if not tokens:
        return True
    meaningful = [tok for tok in tokens if len(tok) > 2]
    if not meaningful:
        return True
    return all(tok in SOFT_SKILLS_ONLY_WORDS for tok in meaningful)


def _check_title(v: VacancySummary) -> list[Issue]:
    issues: list[Issue] = []
    if not v.job_name:
        issues.append(
            Issue(
                topic="название должности",
                issue_type="omission",
                source_field="job-name",
                quote="",
                problem="Не указано название должности.",
                recommendation="Укажите точное наименование должности с профилем или направлением работы.",
            )
        )
    elif v.job_name.lower() in GENERIC_TITLES:
        issues.append(
            Issue(
                topic="название должности",
                issue_type="ambiguity",
                source_field="job-name",
                quote=v.job_name,
                problem="Название должности слишком общее и не отражает профиль работы.",
                recommendation="Уточните специализацию или отдел (например, «Специалист по делопроизводству» или «Специалист отдела кадров»).",
            )
        )
    return issues


def _check_salary(v: VacancySummary) -> list[Issue]:
    issues: list[Issue] = []
    s_min = v.salary_min or 0
    s_max = v.salary_max or 0

    if s_min <= 0 and s_max <= 0:
        issues.append(
            Issue(
                topic="оплата",
                issue_type="omission",
                source_field="salary_min, salary_max",
                quote="",
                problem="Не указан размер оплаты труда (нижняя и верхняя границы равны 0 или отсутствуют).",
                recommendation="Укажите оклад или вилку заработной платы в рублях и уточните, указана сумма до или после вычета НДФЛ.",
            )
        )
    elif s_min > 0 and s_max > 0 and s_min > s_max:
        issues.append(
            Issue(
                topic="оплата",
                issue_type="contradiction",
                source_field="salary_min, salary_max",
                quote=f"salary_min: {s_min} {v.currency}; salary_max: {s_max} {v.currency}",
                problem="Минимальная зарплата превышает максимальную.",
                recommendation="Проверьте границы вилки оплаты труда и исправьте перепутанные значения.",
            )
        )
    elif s_min > 0 and s_max == 0:
        issues.append(
            Issue(
                topic="оплата",
                issue_type="ambiguity",
                source_field="salary_min, salary_max",
                quote=f"salary_min: {s_min} {v.currency}, salary_max: 0",
                problem="Указана только нижняя граница оплаты без верхнего предела или пояснения структуры дохода.",
                recommendation="Уточните верхнюю границу вилки или укажите, является ли сумма фиксированным окладом, и есть ли премии.",
            )
        )
    elif s_min == 0 and s_max > 0:
        issues.append(
            Issue(
                topic="оплата",
                issue_type="ambiguity",
                source_field="salary_min, salary_max",
                quote=f"salary_min: 0, salary_max: {s_max} {v.currency}",
                problem="Указана только верхняя граница оплаты без гарантированного минимума.",
                recommendation="Укажите минимальный гарантированный оклад и условия достижения верхней границы дохода.",
            )
        )
    return issues


def _check_employment(v: VacancySummary) -> list[Issue]:
    if not v.employment:
        return [
            Issue(
                topic="тип занятости",
                issue_type="omission",
                source_field="employment",
                quote="",
                problem="Не указан тип занятости (полная, частичная, временная или стажировка).",
                recommendation="Уточните тип занятости и долю ставки (например, полная занятость 1,0 ставка или частичная 0,5 ставки).",
            )
        ]
    return []


def _check_schedule(v: VacancySummary) -> list[Issue]:
    issues: list[Issue] = []
    combined_schedule_context = f"{v.schedule} {v.qualification} {v.duty}"
    sched_lower = v.schedule.lower()
    qual_lower = v.qualification.lower()

    if not v.schedule:
        issues.append(
            Issue(
                topic="график",
                issue_type="omission",
                source_field="schedule",
                quote="",
                problem="Не указан график работы.",
                recommendation="Укажите режим работы: рабочие дни недели или схему смен, а также время начала и окончания рабочего дня.",
            )
        )
        return issues

    # Противоречие: в schedule указан «Гибкий график», а в qualification — фиксированная пятидневка с часами
    has_flexible_in_schedule = "гибк" in sched_lower
    has_fixed_in_qual = bool(WEEKDAYS_RE.search(v.qualification) and TIME_RANGE_RE.search(v.qualification))
    if has_flexible_in_schedule and has_fixed_in_qual:
        issues.append(
            Issue(
                topic="график",
                issue_type="contradiction",
                source_field="schedule, requirement.qualification",
                quote=f'schedule: "{v.schedule}" | requirement.qualification: "{v.qualification}"',
                problem="Поле графика указывает «Гибкий график», тогда как в описании квалификации указана фиксированная пятидневная неделя с конкретными часами и без правил гибкости.",
                recommendation="Уточните, какой режим является основным, и опишите конкретные правила гибкого графика (допустимое окно начала дня, обязательные часы присутствия).",
            )
        )
        return issues

    has_time = bool(TIME_RANGE_RE.search(combined_schedule_context))
    has_shift_pattern = bool(SHIFT_PATTERN_RE.search(combined_schedule_context))
    has_weekdays = bool(WEEKDAYS_RE.search(combined_schedule_context))

    if has_flexible_in_schedule:
        issues.append(
            Issue(
                topic="график",
                issue_type="ambiguity",
                source_field="schedule",
                quote=v.schedule,
                problem="Указан «гибкий график» без уточнения рабочих дней, продолжительности смен или обязательных часов.",
                recommendation="Уточните количество рабочих дней или часов в неделю, диапазон времени начала/окончания работы и порядок согласования смен.",
            )
        )
    elif "сменн" in sched_lower and not (has_shift_pattern and has_time):
        issues.append(
            Issue(
                topic="график",
                issue_type="ambiguity",
                source_field="schedule",
                quote=v.schedule,
                problem="Указан сменный график без схемы чередования смен и времени работы.",
                recommendation="Уточните схему смен (например, 2/2 или 1/3), длительность смены, время начала и окончания, наличие ночных смен.",
            )
        )
    elif "полный рабочий день" in sched_lower and not has_time:
        missing_parts = []
        if not has_weekdays:
            missing_parts.append("рабочие дни недели")
        missing_parts.append("часы начала и окончания работы")
        issues.append(
            Issue(
                topic="график",
                issue_type="ambiguity",
                source_field="schedule",
                quote=v.schedule,
                problem=f"Не указаны {' и '.join(missing_parts)}.",
                recommendation="Уточните конкретное расписание: дни недели (например, пн–пт) и точные часы работы (например, с 09:00 до 18:00).",
            )
        )
    elif "без уточнения правил" in qual_lower:
        issues.append(
            Issue(
                topic="график",
                issue_type="ambiguity",
                source_field="requirement.qualification",
                quote=v.qualification,
                problem="Упоминается гибкий график без пояснения правил его применения.",
                recommendation="Уточните границы гибкого графика и порядок согласования рабочих часов.",
            )
        )

    return issues


def _check_duty(v: VacancySummary) -> list[Issue]:
    issues: list[Issue] = []
    if not v.duty:
        issues.append(
            Issue(
                topic="обязанности",
                issue_type="omission",
                source_field="duty",
                quote="",
                problem="Не описаны должностные обязанности.",
                recommendation="Перечислите 3–5 основных регулярных задач, которые будет выполнять сотрудник.",
            )
        )
        return issues

    for pattern in VAGUE_DUTY_PATTERNS:
        if re.search(pattern, v.duty, re.IGNORECASE):
            issues.append(
                Issue(
                    topic="обязанности",
                    issue_type="ambiguity",
                    source_field="duty",
                    quote=v.duty,
                    problem="Обязанности сформулированы слишком расплывчато и не дают представления о реальном содержании работы.",
                    recommendation="Замените общие формулировки на конкретный перечень ежедневных задач, систем и зон ответственности.",
                )
            )
            break

    return issues


def _check_requirements(v: VacancySummary) -> list[Issue]:
    issues: list[Issue] = []

    # 1. Противоречие между requirement.experience == 0 и текстом qualification / requirements
    if v.experience is not None and v.experience == 0:
        for field_name, text in (
            ("requirement.qualification", v.qualification),
            ("requirements", v.requirements),
        ):
            if not text:
                continue
            # Явно указано "не менее N лет опыта" (N >= 1)
            years_match = EXPERIENCE_YEARS_RE.search(text)
            if years_match and int(years_match.group(1)) > 0:
                issues.append(
                    Issue(
                        topic="требования",
                        issue_type="contradiction",
                        source_field=f"requirement.experience, {field_name}",
                        quote=f'requirement.experience: {v.experience} | {field_name}: "{text}"',
                        problem=(
                            f"В структурированном поле указано «опыт 0 лет», тогда как в «{field_name}» "
                            f"требуется опыт не менее {years_match.group(1)} лет."
                        ),
                        recommendation="Согласуйте требование к стажу: исправьте поле requirement.experience либо уберите требование многолетнего опыта из описания.",
                    )
                )
                break

            # Требуется практический опыт в requirements (но НЕ «опыт не обязателен» и НЕ «опыт приветствуется»)
            lowered = text.lower()
            if (
                EXPERIENCE_REQUIRED_PHRASE_RE.search(text)
                and "не обязател" not in lowered
                and "без опыта" not in lowered
                and "приветствуется" not in lowered
            ):
                issues.append(
                    Issue(
                        topic="требования",
                        issue_type="contradiction",
                        source_field=f"requirement.experience, {field_name}",
                        quote=f'requirement.experience: {v.experience} | {field_name}: "{text}"',
                        problem=(
                            f"В структурированном поле указан нулевой опыт (0 лет), но в «{field_name}» "
                            "указано требование наличия профильного опыта."
                        ),
                        recommendation="Уточните, является ли профильный опыт обязательным (и укажите минимальный срок в годах) либо только желательным.",
                    )
                )
                break

    # 2. Скрытые условия «обсуждаются на собеседовании» в qualification
    for pattern in HIDDEN_CONDITIONS_PATTERNS:
        if re.search(pattern, v.qualification, re.IGNORECASE) and "адрес" not in v.qualification.lower() and "формат" not in v.qualification.lower():
            issues.append(
                Issue(
                    topic="требования",
                    issue_type="ambiguity",
                    source_field="requirement.qualification",
                    quote=v.qualification,
                    problem="Конкретные квалификационные требования и условия работы скрыты за отсылкой к собеседованию.",
                    recommendation="Раскройте базовые требования к образованию, опыту и профессиональным навыкам непосредственно в тексте вакансии.",
                )
            )
            break

    # 3. Пустые или слишком общие требования (только личностные качества без проф. навыков)
    if not v.requirements and not v.qualification and (not v.education or v.education.lower() == "не указано"):
        issues.append(
            Issue(
                topic="требования",
                issue_type="omission",
                source_field="requirements, requirement",
                quote="",
                problem="Не указаны требования к кандидату (ни профессиональные навыки, ни образование).",
                recommendation="Укажите необходимые профессиональные навыки, инструменты и требования к образованию (или явно отметьте, что обучение проводится на месте).",
            )
        )
    elif v.requirements and _is_soft_skills_only(v.requirements) and (
        not v.education or v.education.lower() == "не указано"
    ) and "обучен" not in v.qualification.lower():
        issues.append(
            Issue(
                topic="требования",
                issue_type="ambiguity",
                source_field="requirements, requirement.qualification",
                quote=f'{v.requirements} | {v.qualification}' if v.qualification else v.requirements,
                problem="Указаны только общие личностные качества без конкретных профессиональных навыков и требований к образованию.",
                recommendation="Уточните необходимые рабочие навыки (например, знание офисных программ, систем учёта) и требуемый уровень образования.",
            )
        )

    return issues


def _check_workplace(v: VacancySummary) -> list[Issue]:
    issues: list[Issue] = []
    combined_address = "; ".join(v.addresses)

    # 1. Противоречие: дистанционная работа в одном поле и обязательный офис в другом
    has_remote_duty = bool(REMOTE_PHRASE_RE.search(v.duty))
    has_office_qual = bool(OFFICE_MANDATORY_RE.search(v.qualification))
    has_remote_qual = bool(REMOTE_PHRASE_RE.search(v.qualification))
    has_office_duty = bool(OFFICE_MANDATORY_RE.search(v.duty))

    if (has_remote_duty and has_office_qual) or (has_remote_qual and has_office_duty):
        issues.append(
            Issue(
                topic="место работы",
                issue_type="contradiction",
                source_field="duty, requirement.qualification",
                quote=f'duty: "{v.duty}" | requirement.qualification: "{v.qualification}"',
                problem="В описании обязанностей указана полностью дистанционная работа, а в требованиях — обязательное ежедневное присутствие в офисе.",
                recommendation="Уточните фактический формат работы (офис, гибрид или полностью удалённо) и уберите противоречащую формулировку.",
            )
        )
        return issues

    # 2. В тексте явно сказано, что формат и адрес уточняются на собеседовании
    if (
        ("адрес" in v.qualification.lower() or "формат" in v.qualification.lower())
        and any(re.search(p, v.qualification, re.IGNORECASE) for p in HIDDEN_CONDITIONS_PATTERNS)
    ):
        issues.append(
            Issue(
                topic="место работы",
                issue_type="ambiguity",
                source_field="addresses.address, requirement.qualification",
                quote=f'addresses: "{combined_address}" | requirement.qualification: "{v.qualification}"',
                problem="Не указаны точный адрес рабочего места и формат работы (офис, гибрид или дистанционно) — сведения отложены до собеседования.",
                recommendation="Укажите конкретный адрес рабочего места (улицу/район) и формат работы до этапа собеседования.",
            )
        )
        return issues

    # 3. Отсутствует адрес вообще
    if not v.addresses:
        issues.append(
            Issue(
                topic="место работы",
                issue_type="omission",
                source_field="addresses.address",
                quote="",
                problem="Не указано место работы.",
                recommendation="Укажите населённый пункт, адрес рабочего места или явно обозначьте дистанционный формат работы.",
            )
        )
        return issues

    # 4. Указан только регион или только город без улицы/дома (и не указана удалёнка)
    has_street = any(STREET_DETAIL_RE.search(addr) for addr in v.addresses)
    is_remote_any = bool(REMOTE_PHRASE_RE.search(f"{v.duty} {v.qualification} {v.schedule}"))
    if not has_street and not is_remote_any:
        is_region_only = all(
            "область" in addr.lower() and "г." not in addr.lower() and "город" not in addr.lower()
            for addr in v.addresses
        )
        if is_region_only:
            issues.append(
                Issue(
                    topic="место работы",
                    issue_type="omission",
                    source_field="addresses.address",
                    quote="",
                    problem=f"Указан только регион («{combined_address}») без города и адреса рабочего места.",
                    recommendation="Укажите конкретный населённый пункт, улицу/район и формат работы (в офисе, разъездной или дистанционно).",
                )
            )
        else:
            issues.append(
                Issue(
                    topic="место работы",
                    issue_type="ambiguity",
                    source_field="addresses.address",
                    quote=combined_address,
                    problem="Указан только населённый пункт без адреса рабочего места или ориентира (района) и без указания формата работы.",
                    recommendation="Уточните точный адрес или район рабочего места, а также формат присутствия (офис, гибрид, разъездной).",
                )
            )

    return issues


def run_rule_checks(vacancy: VacancySummary) -> list[Issue]:
    """Запускает полный набор детерминированных проверок по 7 критериям задания."""
    issues: list[Issue] = []
    issues.extend(_check_title(vacancy))
    issues.extend(_check_duty(vacancy))
    issues.extend(_check_requirements(vacancy))
    issues.extend(_check_salary(vacancy))
    issues.extend(_check_schedule(vacancy))
    issues.extend(_check_workplace(vacancy))
    issues.extend(_check_employment(vacancy))
    return issues
