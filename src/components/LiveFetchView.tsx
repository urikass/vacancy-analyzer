import { useState } from 'react';
import { RefreshCw, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import type { AnalysisReport, EnvStatus } from '../types';

interface LiveFetchViewProps {
  envStatus: EnvStatus;
  onReportLoaded: (report: AnalysisReport) => void;
  onGoToReport: () => void;
}

interface FetchResponse {
  status: 'ok' | 'error';
  message?: string;
  error?: string;
  preserved_last_report?: boolean;
  report_path?: string | null;
  report?: AnalysisReport | null;
}

export function LiveFetchView({
  envStatus,
  onReportLoaded,
  onGoToReport,
}: LiveFetchViewProps) {
  const [apiUrl, setApiUrl] = useState(envStatus.defaultApiUrl);
  const [maxVacancies, setMaxVacancies] = useState(20);
  const [pageSize, setPageSize] = useState(10);
  const [scheduleMinutes, setScheduleMinutes] = useState(60);
  const [provider, setProvider] = useState<'rules' | 'ollama' | 'gigachat'>('rules');
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<FetchResponse | null>(null);

  const handleRunLive = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsRunning(true);
    setResult(null);
    try {
      const resp = await fetch('/api/fetch-live', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: apiUrl,
          maxVacancies,
          pageSize,
          provider,
        }),
      });
      const data: FetchResponse = await resp.json();
      setResult(data);
      if (data.status === 'ok' && data.report) {
        onReportLoaded(data.report);
      }
    } catch (err) {
      setResult({
        status: 'error',
        error: err instanceof Error ? err.message : 'Сетевая ошибка при запуске сбора.',
      });
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="pb-5 border-b border-slate-200">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Рабочий режим: сбор с API «Работа в России»
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Постраничная загрузка вакансий Калининградской области (минимум 2 страницы при достаточном лимите), дедупликация по ID и сохранение последнего успешного отчёта при сбое API.
        </p>
      </div>

      <form
        onSubmit={handleRunLive}
        className="bg-white border border-slate-200 rounded-xl p-6 space-y-5"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="md:col-span-2">
            <label
              htmlFor="api-url-input"
              className="block text-xs font-semibold text-slate-700 mb-1.5"
            >
              URL источника API региона 39
            </label>
            <input
              id="api-url-input"
              type="url"
              required
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="w-full h-10 px-3 rounded-lg border border-slate-300 font-mono text-xs text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-700"
            />
          </div>

          <div>
            <label
              htmlFor="max-vacancies-input"
              className="block text-xs font-semibold text-slate-700 mb-1.5"
            >
              Максимальное число вакансий
            </label>
            <input
              id="max-vacancies-input"
              type="number"
              min={2}
              max={100}
              value={maxVacancies}
              onChange={(e) => setMaxVacancies(Number(e.target.value))}
              className="w-full h-10 px-3 rounded-lg border border-slate-300 text-sm tabular-nums text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-700"
            />
          </div>

          <div>
            <label
              htmlFor="page-size-input"
              className="block text-xs font-semibold text-slate-700 mb-1.5"
            >
              Размер страницы (для загрузки 2+ страниц)
            </label>
            <input
              id="page-size-input"
              type="number"
              min={1}
              max={50}
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              className="w-full h-10 px-3 rounded-lg border border-slate-300 text-sm tabular-nums text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-700"
            />
          </div>

          <div>
            <label
              htmlFor="schedule-interval-input"
              className="block text-xs font-semibold text-slate-700 mb-1.5"
            >
              Интервал расписания (минуты)
            </label>
            <input
              id="schedule-interval-input"
              type="number"
              min={5}
              max={1440}
              value={scheduleMinutes}
              onChange={(e) => setScheduleMinutes(Number(e.target.value))}
              className="w-full h-10 px-3 rounded-lg border border-slate-300 text-sm tabular-nums text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-700"
            />
          </div>

          <div>
            <label
              htmlFor="live-provider-select"
              className="block text-xs font-semibold text-slate-700 mb-1.5"
            >
              Провайдер ИИ для анализа
            </label>
            <select
              id="live-provider-select"
              value={provider}
              onChange={(e) =>
                setProvider(e.target.value as 'rules' | 'ollama' | 'gigachat')
              }
              className="w-full h-10 px-3 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-700"
            >
              <option value="rules">Базовые правила (быстро)</option>
              <option value="ollama">Ollama ({envStatus.ollamaModel})</option>
              <option value="gigachat">
                GigaChat API ({envStatus.gigachatConfigured ? 'ключ задан' : 'нужен ключ в .env'})
              </option>
            </select>
          </div>
        </div>

        <div className="pt-2 flex flex-wrap items-center justify-between gap-4 border-t border-slate-200">
          <div className="text-xs text-slate-500 flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400 shrink-0" />
            Команда планировщика:{' '}
            <code className="font-mono text-slate-800">
              python -m backend.cli schedule --interval-minutes {scheduleMinutes}
            </code>
          </div>

          <button
            type="submit"
            disabled={isRunning}
            className="inline-flex items-center gap-2 h-10 px-5 rounded-lg bg-blue-700 text-white text-sm font-semibold hover:bg-blue-800 disabled:opacity-50 transition-colors whitespace-nowrap shrink-0 focus-visible:outline-2 focus-visible:outline-blue-700"
          >
            <RefreshCw className={`w-4 h-4 ${isRunning ? 'animate-spin' : ''}`} />
            {isRunning ? 'Загружаем с портала...' : 'Запустить ручной сбор'}
          </button>
        </div>
      </form>

      {result && (
        <div
          role={result.status === 'ok' ? 'status' : 'alert'}
          className={`rounded-xl border p-5 space-y-3 ${
            result.status === 'ok'
              ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
              : 'bg-amber-50/70 border-amber-200 text-amber-950'
          }`}
        >
          <div className="flex items-start gap-3">
            {result.status === 'ok' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-700 shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
            )}
            <div className="space-y-1 text-sm">
              <div className="font-semibold">
                {result.status === 'ok'
                  ? 'Сбор с портала «Работа в России» выполнен'
                  : 'Не удалось связаться с порталом «Работа в России»'}
              </div>
              <p className="text-slate-700">
                {result.message || result.error}
              </p>
              {result.preserved_last_report && (
                <p className="text-xs text-slate-600">
                  Последний успешный отчёт остался нетронутым: <code className="font-mono">{result.report_path}</code>
                </p>
              )}
            </div>
          </div>

          {result.status === 'ok' && (
            <button
              type="button"
              onClick={onGoToReport}
              className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800"
            >
              Открыть загруженный отчёт
            </button>
          )}
        </div>
      )}
    </div>
  );
}
