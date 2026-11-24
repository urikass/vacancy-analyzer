import type { FilterKey, IssueType, RawVacancy, VacancyReportItem } from '../types';

export interface ReportCounts {
  total: number;
  clean: number;
  withIssues: number;
  contradictions: number;
  omissions: number;
  ambiguities: number;
  totalIssues: number;
}

export function computeReportCounts(vacancies: VacancyReportItem[]): ReportCounts {
  let clean = 0;
  let withIssues = 0;
  let contradictions = 0;
  let omissions = 0;
  let ambiguities = 0;
  let totalIssues = 0;

  for (const item of vacancies) {
    if (item.issues.length === 0) {
      clean += 1;
    } else {
      withIssues += 1;
    }
    for (const issue of item.issues) {
      totalIssues += 1;
      if (issue.issue_type === 'contradiction') contradictions += 1;
      else if (issue.issue_type === 'omission') omissions += 1;
      else if (issue.issue_type === 'ambiguity') ambiguities += 1;
    }
  }

  return {
    total: vacancies.length,
    clean,
    withIssues,
    contradictions,
    omissions,
    ambiguities,
    totalIssues,
  };
}

export function filterVacancies(
  vacancies: VacancyReportItem[],
  filter: FilterKey,
  searchQuery: string,
): VacancyReportItem[] {
  const query = searchQuery.trim().toLowerCase();

  return vacancies.filter((item) => {
    if (filter === 'clean' && item.issues.length > 0) return false;
    if (filter === 'with_issues' && item.issues.length === 0) return false;
    if (
      (filter === 'contradiction' || filter === 'omission' || filter === 'ambiguity') &&
      !item.issues.some((i) => i.issue_type === filter)
    ) {
      return false;
    }

    if (!query) return true;
    const haystack = [
      item.vacancy_id,
      item.job_name,
      item.company_name,
      ...item.issues.map((i) => `${i.topic} ${i.problem} ${i.source_field}`),
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(query);
  });
}

export function getSafeHttpUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.toString();
    }
    return null;
  } catch {
    return null;
  }
}

export function getIssueTypeLabel(issueType: IssueType): string {
  switch (issueType) {
    case 'contradiction':
      return 'Противоречие';
    case 'omission':
      return 'Пропуск';
    case 'ambiguity':
      return 'Неоднозначность';
  }
}

export function formatSalaryRange(raw?: RawVacancy): string {
  if (!raw) return '—';
  const min = Number(raw.salary_min ?? 0);
  const max = Number(raw.salary_max ?? 0);
  const cur = raw.currency || 'RUB';
  if (min <= 0 && max <= 0) return 'Не указана (0)';
  if (min > 0 && max > 0 && min === max) return `${min.toLocaleString('ru-RU')} ${cur}`;
  if (min > 0 && max > 0) return `${min.toLocaleString('ru-RU')} – ${max.toLocaleString('ru-RU')} ${cur}`;
  if (min > 0) return `от ${min.toLocaleString('ru-RU')} ${cur} (верх не указан)`;
  return `до ${max.toLocaleString('ru-RU')} ${cur}`;
}

export function buildEmployerLetter(item: VacancyReportItem): string {
  if (item.issues.length === 0) {
    return `Здравствуйте!\n\nВакансия «${item.job_name}» (${item.vacancy_id}) проверена редактором — условия описаны понятно, уточнений не требуется.`;
  }

  const lines = [
    'Здравствуйте!',
    '',
    `При проверке вакансии «${item.job_name}» (ID: ${item.vacancy_id}) на портале «Работа в России» мы подготовили несколько уточнений, которые помогут соискателям быстрее понять условия работы:`,
    '',
  ];

  item.issues.forEach((issue, idx) => {
    lines.push(`${idx + 1}. ${capitalizeFirst(issue.topic)} (${getIssueTypeLabel(issue.issue_type).toLowerCase()}):`);
    lines.push(`   Проблема: ${issue.problem}`);
    lines.push(`   Просим уточнить: ${issue.recommendation}`);
  });

  lines.push('', 'Будем благодарны за обновление карточки вакансии.');
  return lines.join('\n');
}

function capitalizeFirst(value: string): string {
  if (!value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}
