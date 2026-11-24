import { useMemo, useRef, useState } from 'react';
import {
  Upload,
  Download,
  Search,
  Copy,
  Check,
  ExternalLink,
  AlertTriangle,
  HelpCircle,
  AlertOctagon,
  CheckCircle2,
} from 'lucide-react';
import type {
  AnalysisReport,
  FilterKey,
  Issue,
  RawVacancy,
  VacancyReportItem,
} from '../types';
import {
  buildEmployerLetter,
  computeReportCounts,
  filterVacancies,
  formatSalaryRange,
  getIssueTypeLabel,
  getSafeHttpUrl,
} from '../utils/reportHelpers';

interface ReportViewProps {
  report: AnalysisReport;
  rawVacancies: RawVacancy[];
  isAnalyzing: boolean;
  errorMessage: string | null;
  provider: 'rules' | 'ollama' | 'gigachat';
  onProviderChange: (provider: 'rules' | 'ollama' | 'gigachat') => void;
  onUploadJson: (payload: unknown, fileName: string) => Promise<void>;
  onResetDemo: () => Promise<void>;
}

const FILTER_OPTIONS: Array<{ key: FilterKey; label: string }> = [
  { key: 'all', label: 'Все' },
  { key: 'with_issues', label: 'С замечаниями' },
  { key: 'contradiction', label: 'Противоречия' },
  { key: 'omission', label: 'Пропуски' },
  { key: 'ambiguity', label: 'Неоднозначности' },
  { key: 'clean', label: 'Без замечаний' },
];

function IssueTypeText({ type }: { type: Issue['issue_type'] }) {
  if (type === 'contradiction') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-red-700">
        <AlertOctagon className="w-3.5 h-3.5 shrink-0" />
        {getIssueTypeLabel(type)}
      </span>
    );
  }
  if (type === 'omission') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-700">
        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
        {getIssueTypeLabel(type)}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-sky-700">
      <HelpCircle className="w-3.5 h-3.5 shrink-0" />
      {getIssueTypeLabel(type)}
    </span>
  );
}

export function ReportView({
  report,
  rawVacancies,
  isAnalyzing,
  errorMessage,
  provider,
  onProviderChange,
  onUploadJson,
  onResetDemo,
}: ReportViewProps) {
  const [filter, setFilter] = useState<FilterKey>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string>(
    report.vacancies.find((v) => v.issues.length > 0)?.vacancy_id ??
      report.vacancies[0]?.vacancy_id ??
      '',
  );
  const [copiedLetter, setCopiedLetter] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const counts = useMemo(
    () => computeReportCounts(report.vacancies),
    [report.vacancies],
  );

  const filtered = useMemo(
    () => filterVacancies(report.vacancies, filter, searchQuery),
    [report.vacancies, filter, searchQuery],
  );

  const selectedItem: VacancyReportItem | null = useMemo(() => {
    const exact = filtered.find((v) => v.vacancy_id === selectedId);
    return exact ?? filtered[0] ?? null;
  }, [filtered, selectedId]);

  const selectedRaw: RawVacancy | undefined = useMemo(() => {
    if (!selectedItem) return undefined;
    return rawVacancies.find((r) => String(r.id) === selectedItem.vacancy_id);
  }, [rawVacancies, selectedItem]);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    try {
      const text = (await file.text()).replace(/^\uFEFF/, '');
      const parsed = JSON.parse(text);
      await onUploadJson(parsed, file.name);
    } catch (err) {
      setUploadError(
        err instanceof Error
          ? `Ошибка чтения JSON: ${err.message}`
          : 'Файл не является корректным JSON.',
      );
    } finally {
      event.target.value = '';
    }
  };

  const handleDownloadJson = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'sample_report.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handleCopyLetter = async () => {
    if (!selectedItem) return;
    const text = buildEmployerLetter(selectedItem);
    try {
      await navigator.clipboard.writeText(text);
      setCopiedLetter(true);
      setTimeout(() => setCopiedLetter(false), 2000);
    } catch {
      setCopiedLetter(false);
    }
  };

  const safeCardUrl = getSafeHttpUrl(selectedItem?.vacancy_url);

  return (
    <div className="space-y-6">
      {/* Toolbar: Verification upload, provider select, export */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-5 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Проверочный отчёт по вакансиям
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Источник: <span className="font-mono text-xs text-slate-800">{report.meta.source}</span>
            <span className="mx-2 text-slate-300" aria-hidden="true">·</span>
            Режим: {report.meta.mode === 'working' ? 'Рабочий (API 39)' : 'Проверочный (локальный JSON)'}
            <span className="mx-2 text-slate-300" aria-hidden="true">·</span>
            Анализ: {report.meta.ai_provider}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          <label htmlFor="verify-provider-select" className="sr-only">
            Провайдер анализа
          </label>
          <select
            id="verify-provider-select"
            value={provider}
            onChange={(e) =>
              onProviderChange(e.target.value as 'rules' | 'ollama' | 'gigachat')
            }
            className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 focus-visible:outline-2 focus-visible:outline-blue-700"
          >
            <option value="rules">Правила (быстрая проверка)</option>
            <option value="ollama">Ollama (локальный ИИ)</option>
            <option value="gigachat">GigaChat API (облако)</option>
          </select>

          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            onChange={handleFileChange}
            className="hidden"
          />

          <button
            type="button"
            disabled={isAnalyzing}
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex items-center gap-2 h-10 px-4 rounded-lg bg-blue-700 text-white text-sm font-semibold hover:bg-blue-800 disabled:opacity-50 transition-colors whitespace-nowrap shrink-0 focus-visible:outline-2 focus-visible:outline-blue-700"
          >
            <Upload className="w-4 h-4 shrink-0" />
            {isAnalyzing ? 'Анализируем...' : 'Загрузить JSON'}
          </button>

          <button
            type="button"
            onClick={handleDownloadJson}
            className="inline-flex items-center gap-2 h-10 px-4 rounded-lg border border-slate-300 bg-white text-slate-800 text-sm font-semibold hover:bg-slate-50 transition-colors whitespace-nowrap shrink-0 focus-visible:outline-2 focus-visible:outline-blue-700"
          >
            <Download className="w-4 h-4 shrink-0" />
            Скачать JSON
          </button>
        </div>
      </div>

      {(errorMessage || uploadError) && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 flex items-center justify-between gap-4"
        >
          <span>{uploadError || errorMessage}</span>
          <button
            type="button"
            onClick={() => {
              setUploadError(null);
              void onResetDemo();
            }}
            className="text-xs font-semibold text-red-900 underline whitespace-nowrap shrink-0"
          >
            Вернуть учебный набор
          </button>
        </div>
      )}

      {/* 4-column flat KPI strip with crisp 1px inner hairlines on both mobile and desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-slate-200 border border-slate-200 rounded-xl overflow-hidden">
        <div className="p-5 bg-white">
          <div className="text-xs font-medium text-slate-500">Проверено вакансий</div>
          <div className="mt-1.5 text-2xl font-bold text-slate-900 tabular-nums">
            {counts.total}
          </div>
          <div className="mt-1 text-xs text-slate-500 tabular-nums">
            Без замечаний: {counts.clean} · С замечаниями: {counts.withIssues}
          </div>
        </div>
        <div className="p-5 bg-white">
          <div className="text-xs font-medium text-slate-500">Всего замечаний</div>
          <div className="mt-1.5 text-2xl font-bold text-slate-900 tabular-nums">
            {counts.totalIssues}
          </div>
          <div className="mt-1 text-xs text-slate-500">По 7 критериям задания</div>
        </div>
        <div className="p-5 bg-white">
          <div className="text-xs font-medium text-slate-500">Противоречия</div>
          <div className="mt-1.5 text-2xl font-bold text-red-700 tabular-nums">
            {counts.contradictions}
          </div>
          <div className="mt-1 text-xs text-slate-500">Расхождения между полями</div>
        </div>
        <div className="p-5 bg-white">
          <div className="text-xs font-medium text-slate-500">Пропуски и неясности</div>
          <div className="mt-1.5 text-2xl font-bold text-amber-700 tabular-nums">
            {counts.omissions + counts.ambiguities}
          </div>
          <div className="mt-1 text-xs text-slate-500 tabular-nums">
            Пропусков: {counts.omissions} · Неоднозначностей: {counts.ambiguities}
          </div>
        </div>
      </div>

      {/* Filter bar + Search */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div
          role="tablist"
          aria-label="Фильтр по типу замечаний"
          className="flex flex-wrap items-center gap-1 p-1 bg-slate-100 rounded-lg border border-slate-200"
        >
          {FILTER_OPTIONS.map((opt) => {
            const active = filter === opt.key;
            return (
              <button
                key={opt.key}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setFilter(opt.key)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors whitespace-nowrap shrink-0 focus-visible:outline-2 focus-visible:outline-blue-700 ${
                  active
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        <div className="relative w-full lg:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <label htmlFor="vacancy-search" className="sr-only">
            Поиск по ID, должности или проблеме
          </label>
          <input
            id="vacancy-search"
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по ID, должности, теме..."
            className="w-full h-10 pl-9 pr-3 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-2 focus-visible:outline-blue-700"
          />
        </div>
      </div>

      {/* Master-Detail workspace */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Left: Vacancy list */}
        <div className="xl:col-span-5 bg-white border border-slate-200 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between text-xs font-semibold text-slate-600">
            <span>Список вакансий</span>
            <span className="tabular-nums">Показано: {filtered.length}</span>
          </div>

          {filtered.length === 0 ? (
            <div className="p-8 text-center space-y-3">
              <p className="text-sm text-slate-600">
                По выбранному фильтру вакансий не найдено.
              </p>
              <button
                type="button"
                onClick={() => {
                  setFilter('all');
                  setSearchQuery('');
                }}
                className="px-3.5 py-2 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Сбросить фильтры
              </button>
            </div>
          ) : (
            <ul className="divide-y divide-slate-200 max-h-[640px] overflow-y-auto">
              {filtered.map((item) => {
                const isSelected = selectedItem?.vacancy_id === item.vacancy_id;
                const hasContradiction = item.issues.some(
                  (i) => i.issue_type === 'contradiction',
                );
                return (
                  <li key={item.vacancy_id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(item.vacancy_id)}
                      className={`w-full text-left px-4 py-3.5 transition-colors focus-visible:outline-2 focus-visible:outline-blue-700 ${
                        isSelected ? 'bg-blue-50/70' : 'hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-slate-900 truncate">
                            {item.job_name || 'Без названия'}
                          </div>
                          <div className="mt-1 text-xs text-slate-500 flex items-center gap-1.5 flex-wrap">
                            <span className="font-mono text-slate-700">
                              {item.vacancy_id}
                            </span>
                            <span aria-hidden="true">·</span>
                            <span className="truncate">{item.company_name || 'Работодатель'}</span>
                          </div>
                        </div>

                        <div className="shrink-0 text-right">
                          {item.issues.length === 0 ? (
                            <span className="text-xs font-semibold text-emerald-700 whitespace-nowrap">
                              Без замечаний
                            </span>
                          ) : (
                            <span
                              className={`text-xs font-semibold tabular-nums whitespace-nowrap ${
                                hasContradiction ? 'text-red-700' : 'text-amber-700'
                              }`}
                            >
                              {item.issues.length} замеч.
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Right: Vacancy inspector */}
        <div className="xl:col-span-7 bg-white border border-slate-200 rounded-xl">
          {!selectedItem ? (
            <div className="p-10 text-center text-sm text-slate-500">
              Выберите вакансию слева, чтобы просмотреть разбор замечаний.
            </div>
          ) : (
            <div>
              {/* Header */}
              <div className="p-6 border-b border-slate-200 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-xs font-mono text-slate-500">
                    {selectedItem.vacancy_id}
                    {selectedItem.company_name ? ` · ${selectedItem.company_name}` : ''}
                  </div>
                  <h2 className="mt-1 text-xl font-bold text-slate-900">
                    {selectedItem.job_name}
                  </h2>
                  {safeCardUrl && (
                    <a
                      href={safeCardUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:underline"
                    >
                      Карточка на портале «Работа в России»
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleCopyLetter}
                  className="inline-flex items-center gap-2 h-9 px-3.5 rounded-lg border border-slate-300 bg-white text-xs font-semibold text-slate-800 hover:bg-slate-50 whitespace-nowrap shrink-0 focus-visible:outline-2 focus-visible:outline-blue-700"
                >
                  {copiedLetter ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-700" />
                      Письмо скопировано
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-slate-500" />
                      Скопировать письмо работодателю
                    </>
                  )}
                </button>
              </div>

              {/* Structured API fields summary */}
              {selectedRaw && (
                <div className="px-6 py-4 bg-slate-50/70 border-b border-slate-200 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 text-xs">
                  <div>
                    <span className="text-slate-500">Оплата: </span>
                    <span className="font-semibold text-slate-900 tabular-nums">
                      {formatSalaryRange(selectedRaw)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">Занятость: </span>
                    <span className="font-semibold text-slate-900">
                      {selectedRaw.employment || 'Не указана'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">График: </span>
                    <span className="font-semibold text-slate-900">
                      {selectedRaw.schedule || 'Не указан'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">Опыт / образование: </span>
                    <span className="font-semibold text-slate-900 tabular-nums">
                      {selectedRaw.requirement?.experience ?? '—'} лет ·{' '}
                      {selectedRaw.requirement?.education || 'Не указано'}
                    </span>
                  </div>
                  <div className="sm:col-span-2">
                    <span className="text-slate-500">Адрес: </span>
                    <span className="font-semibold text-slate-900">
                      {(Array.isArray(selectedRaw.addresses?.address)
                        ? selectedRaw.addresses.address
                            .map((a) => (typeof a === 'string' ? a : a?.location))
                            .filter(Boolean)
                            .join('; ')
                        : (selectedRaw.addresses?.address as { location?: string } | undefined)
                            ?.location) || 'Не указан'}
                    </span>
                  </div>
                </div>
              )}

              {/* Issues list */}
              <div className="p-6">
                {selectedItem.issues.length === 0 ? (
                  <div className="py-8 text-center space-y-2">
                    <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
                    <div className="text-base font-semibold text-slate-900">
                      Замечаний не обнаружено
                    </div>
                    <p className="text-sm text-slate-600 max-w-md mx-auto">
                      Условия труда, оплата, график, место работы и требования описаны понятно и без противоречий. В JSON-отчёте возвращается пустой массив <code className="text-xs font-mono">issues: []</code>.
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-200">
                    {selectedItem.issues.map((issue, idx) => (
                      <article key={`${issue.topic}-${idx}`} className="py-5 first:pt-0 last:pb-0 space-y-2.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2.5 text-sm">
                            <span className="font-bold text-slate-900">
                              {issue.topic.charAt(0).toUpperCase() + issue.topic.slice(1)}
                            </span>
                            <span className="text-slate-300" aria-hidden="true">·</span>
                            <IssueTypeText type={issue.issue_type} />
                          </div>
                          <div className="text-xs font-mono text-slate-500">
                            поле: {issue.source_field}
                          </div>
                        </div>

                        <div className="text-xs text-slate-600 leading-relaxed">
                          <span className="font-semibold text-slate-700">Цитата источника:</span>{' '}
                          {issue.quote ? (
                            <span className="font-mono text-slate-800">{issue.quote}</span>
                          ) : (
                            <span className="italic text-slate-400">
                              &quot;&quot; (пусто — зафиксирован пропуск сведений)
                            </span>
                          )}
                        </div>

                        <p className="text-sm text-slate-800 leading-relaxed">
                          <span className="font-semibold text-slate-900">Суть проблемы: </span>
                          {issue.problem}
                        </p>

                        <p className="text-sm text-slate-700 leading-relaxed bg-slate-50 border border-slate-200 rounded-lg px-3.5 py-2.5">
                          <span className="font-semibold text-slate-900">Рекомендация редактору: </span>
                          {issue.recommendation}
                        </p>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
