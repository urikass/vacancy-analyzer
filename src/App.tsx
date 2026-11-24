import { useEffect, useState } from 'react';
import { Sidebar, MobileMenuButton } from './components/Sidebar';
import { ReportView } from './components/ReportView';
import { LiveFetchView } from './components/LiveFetchView';
import { ResumeTailorView } from './components/ResumeTailorView';
import { DeliveryGuideView } from './components/DeliveryGuideView';
import type {
  ActiveTab,
  AnalysisReport,
  CandidateProfile,
  EnvStatus,
  RawVacancy,
} from './types';

const TAB_BREADCRUMBS: Record<ActiveTab, string> = {
  report: 'Регион 39 / Проверка отчёта',
  live: 'Регион 39 / Сбор с API',
  resume: 'Регион 39 / Черновик резюме',
  guide: 'Регион 39 / Запуск и сдача',
};

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('report');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [rawVacancies, setRawVacancies] = useState<RawVacancy[]>([]);
  const [candidates, setCandidates] = useState<CandidateProfile[]>([]);
  const [envStatus, setEnvStatus] = useState<EnvStatus>({
    gigachatConfigured: false,
    ollamaUrl: 'http://127.0.0.1:11434',
    ollamaModel: 'qwen2.5:7b',
    defaultApiUrl: 'http://opendata.trudvsem.ru/api/v1/vacancies/region/39',
  });

  const [provider, setProvider] = useState<'rules' | 'ollama' | 'gigachat'>('rules');
  const [isLoadingInitial, setIsLoadingInitial] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadInitialData = async () => {
    setIsLoadingInitial(true);
    setErrorMessage(null);
    try {
      const resp = await fetch('/api/initial-data');
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || 'Не удалось загрузить учебные данные.');
      }
      setReport(data.report);
      setRawVacancies(data.rawVacancies ?? []);
      setCandidates(data.candidates ?? []);
      if (data.envStatus) setEnvStatus(data.envStatus);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Ошибка загрузки данных с сервера.',
      );
    } finally {
      setIsLoadingInitial(false);
    }
  };

  useEffect(() => {
    void loadInitialData();
  }, []);

  const handleUploadJson = async (payload: unknown, fileName: string) => {
    setIsAnalyzing(true);
    setErrorMessage(null);
    try {
      const resp = await fetch('/api/analyze-json', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload, provider }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || `Ошибка анализа файла ${fileName}.`);
      }
      setReport({
        ...data.report,
        meta: { ...data.report.meta, source: fileName },
      });
      setRawVacancies(data.rawVacancies ?? []);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Ошибка анализа JSON.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        totalVacancies={report?.meta.total_vacancies ?? 0}
        totalIssues={report?.meta.total_issues ?? 0}
        mobileOpen={mobileMenuOpen}
        onToggleMobile={() => setMobileMenuOpen((prev) => !prev)}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="h-14 bg-white border-b border-slate-200 px-4 sm:px-8 flex items-center justify-between gap-4 sticky top-0 z-20">
          <div className="flex items-center gap-3 min-w-0">
            <MobileMenuButton onClick={() => setMobileMenuOpen(true)} />
            <span className="text-sm font-semibold text-slate-700 truncate">
              {TAB_BREADCRUMBS[activeTab]}
            </span>
          </div>

          <div className="text-xs text-slate-500 whitespace-nowrap shrink-0">
            КАНТКОД · Работа в России
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-8 max-w-[1320px] w-full mx-auto">
          {isLoadingInitial ? (
            <div className="space-y-4 animate-pulse" aria-busy="true">
              <div className="h-8 w-72 bg-slate-200 rounded-md" />
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="h-24 bg-white border border-slate-200 rounded-xl" />
                <div className="h-24 bg-white border border-slate-200 rounded-xl" />
                <div className="h-24 bg-white border border-slate-200 rounded-xl" />
                <div className="h-24 bg-white border border-slate-200 rounded-xl" />
              </div>
              <div className="h-96 bg-white border border-slate-200 rounded-xl" />
            </div>
          ) : !report ? (
            <div className="bg-white border border-slate-200 rounded-xl p-8 text-center space-y-4">
              <p className="text-sm text-red-700">
                {errorMessage || 'Отчёт не загружен.'}
              </p>
              <button
                type="button"
                onClick={() => void loadInitialData()}
                className="px-4 py-2 rounded-lg bg-blue-700 text-white text-sm font-semibold hover:bg-blue-800"
              >
                Повторить загрузку
              </button>
            </div>
          ) : (
            <>
              {activeTab === 'report' && (
                <ReportView
                  report={report}
                  rawVacancies={rawVacancies}
                  isAnalyzing={isAnalyzing}
                  errorMessage={errorMessage}
                  provider={provider}
                  onProviderChange={setProvider}
                  onUploadJson={handleUploadJson}
                  onResetDemo={loadInitialData}
                />
              )}

              {activeTab === 'live' && (
                <LiveFetchView
                  envStatus={envStatus}
                  onReportLoaded={(newReport) => setReport(newReport)}
                  onGoToReport={() => setActiveTab('report')}
                />
              )}

              {activeTab === 'resume' && (
                <ResumeTailorView
                  rawVacancies={rawVacancies}
                  candidates={candidates}
                  provider={provider}
                />
              )}

              {activeTab === 'guide' && <DeliveryGuideView report={report} />}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
