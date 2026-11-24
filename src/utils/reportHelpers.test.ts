import test from 'node:test';
import assert from 'node:assert/strict';
import type { VacancyReportItem } from '../types';
import {
  buildEmployerLetter,
  computeReportCounts,
  filterVacancies,
  formatSalaryRange,
  getSafeHttpUrl,
} from './reportHelpers';

const SAMPLE_ITEMS: VacancyReportItem[] = [
  {
    vacancy_id: 'DEMO-39-001',
    vacancy_url: 'https://trudvsem.ru/vacancy/card/1',
    job_name: 'Специалист по документообороту',
    company_name: 'Учебная организация «Балтика»',
    issues: [],
  },
  {
    vacancy_id: 'DEMO-39-002',
    vacancy_url: null,
    job_name: 'Помощник администратора',
    company_name: 'Учебная организация «Балтика»',
    issues: [
      {
        topic: 'оплата',
        issue_type: 'omission',
        source_field: 'salary_min, salary_max',
        quote: '',
        problem: 'Не указан размер оплаты труда.',
        recommendation: 'Укажите оклад или вилку заработной платы.',
        detected_by: 'rules',
      },
      {
        topic: 'график',
        issue_type: 'ambiguity',
        source_field: 'schedule',
        quote: 'Гибкий график',
        problem: 'Не указаны дни и часы.',
        recommendation: 'Уточните рабочие часы.',
        detected_by: 'rules',
      },
    ],
  },
  {
    vacancy_id: 'DEMO-39-004',
    vacancy_url: null,
    job_name: 'Оператор контактного центра',
    company_name: 'Учебная организация «Балтика»',
    issues: [
      {
        topic: 'место работы',
        issue_type: 'contradiction',
        source_field: 'duty, requirement.qualification',
        quote: 'дистанционная | в офисе',
        problem: 'Противоречие между удалёнкой и офисом.',
        recommendation: 'Уточните формат работы.',
        detected_by: 'rules',
      },
    ],
  },
];

test('computeReportCounts aggregates issue categories accurately', () => {
  const counts = computeReportCounts(SAMPLE_ITEMS);
  assert.equal(counts.total, 3);
  assert.equal(counts.clean, 1);
  assert.equal(counts.withIssues, 2);
  assert.equal(counts.omissions, 1);
  assert.equal(counts.ambiguities, 1);
  assert.equal(counts.contradictions, 1);
  assert.equal(counts.totalIssues, 3);
});

test('filterVacancies filters by issue type and search query', () => {
  assert.equal(filterVacancies(SAMPLE_ITEMS, 'clean', '').length, 1);
  assert.equal(filterVacancies(SAMPLE_ITEMS, 'contradiction', '')[0]?.vacancy_id, 'DEMO-39-004');
  assert.equal(filterVacancies(SAMPLE_ITEMS, 'all', 'администратор')[0]?.vacancy_id, 'DEMO-39-002');
});

test('getSafeHttpUrl blocks javascript and data URLs', () => {
  assert.equal(getSafeHttpUrl('https://trudvsem.ru/vacancy/1'), 'https://trudvsem.ru/vacancy/1');
  assert.equal(getSafeHttpUrl('javascript:alert(1)'), null);
  assert.equal(getSafeHttpUrl('data:text/html,<h1>x</h1>'), null);
  assert.equal(getSafeHttpUrl(null), null);
});

test('formatSalaryRange formats missing, fixed, and range salaries', () => {
  assert.equal(formatSalaryRange({ id: '1', salary_min: 0, salary_max: 0, currency: 'RUB' }), 'Не указана (0)');
  assert.match(formatSalaryRange({ id: '2', salary_min: 38000, salary_max: 38000, currency: 'RUB' }), /38\s000 RUB/);
  assert.match(formatSalaryRange({ id: '3', salary_min: 45000, salary_max: 55000, currency: 'RUB' }), /45\s000.*55\s000 RUB/);
});

test('buildEmployerLetter includes numbered clarification questions', () => {
  const letter = buildEmployerLetter(SAMPLE_ITEMS[1]);
  assert.match(letter, /DEMO-39-002/);
  assert.match(letter, /1\. Оплата \(пропуск\)/);
  assert.match(letter, /2\. График \(неоднозначность\)/);
});
