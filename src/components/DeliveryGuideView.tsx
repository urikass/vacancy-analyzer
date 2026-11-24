import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import type { AnalysisReport } from '../types';

interface DeliveryGuideViewProps {
  report: AnalysisReport;
}

const COMMANDS = [
  {
    id: 'ollama',
    title: '1. Проверочный режим с локальной ИИ (Ollama — бесплатно для жюри)',
    description: 'Загрузите модель qwen2.5:7b один раз, затем прогоните локальный JSON без запросов к порталу.',
    code: `ollama pull qwen2.5:7b
$env:LLM_PROVIDER="ollama"
$env:OLLAMA_MODEL="qwen2.5:7b"
python -m backend.cli check --input sample_data/demo_vacancies.json --output output/sample_report.json`,
  },
  {
    id: 'gigachat',
    title: '2. Проверочный режим через GigaChat API (Сбер)',
    description: 'Скопируйте .env.example в .env, вставьте GIGACHAT_AUTH_KEY локально (не коммитить в Git!).',
    code: `Copy-Item .env.example .env
python -m backend.cli check --input sample_data/demo_vacancies.json --output output/sample_report.json --provider gigachat`,
  },
  {
    id: 'fetch',
    title: '3. Рабочий режим: ручной сбор (2+ страницы) и планировщик',
    description: 'Получает вакансии региона 39 постранично и сохраняет прошлый отчёт, если API недоступен.',
    code: `python -m backend.cli fetch --max-vacancies 40 --page-size 20 --output output/latest_report.json
python -m backend.cli schedule --interval-minutes 60`,
  },
  {
    id: 'tests',
    title: '4. Автотесты Python и скрипт для записи видео',
    description: 'Проверяет все 10 учебных вакансий, идемпотентность, пагинацию, защиту от сбоев API и черновик резюме.',
    code: `python -m unittest discover -s backend/tests -v
.\\scripts\\run_demo.ps1`,
  },
];

export function DeliveryGuideView({ report }: DeliveryGuideViewProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyText = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1800);
    } catch {
      setCopiedId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="pb-5 border-b border-slate-200">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Запуск в PowerShell и материалы для сдачи
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Точка входа бэкенда: <code className="font-mono text-xs text-slate-900">backend/cli.py</code>. Все команды готовы для демонстрации в PowerShell и проверки жюри.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {COMMANDS.map((cmd) => (
          <section
            key={cmd.id}
            className="bg-white border border-slate-200 rounded-xl p-5 flex flex-col justify-between gap-3"
          >
            <div>
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-sm font-bold text-slate-900">{cmd.title}</h2>
                <button
                  type="button"
                  onClick={() => copyText(cmd.id, cmd.code)}
                  aria-label={`Скопировать команду: ${cmd.title}`}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900 shrink-0"
                >
                  {copiedId === cmd.id ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-700" />
                      Скопировано
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      Копировать
                    </>
                  )}
                </button>
              </div>
              <p className="mt-1 text-xs text-slate-600">{cmd.description}</p>
            </div>

            <pre className="p-3.5 rounded-lg bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
              <code>{cmd.code}</code>
            </pre>
          </section>
        ))}
      </div>

      <section className="bg-white border border-slate-200 rounded-xl p-6 space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Предпросмотр текущего JSON-отчёта
            </h2>
            <p className="text-xs text-slate-500">
              Структура соответствует требованиям КАНТКОД и описана в README.md.
            </p>
          </div>
          <button
            type="button"
            onClick={() => copyText('json-full', JSON.stringify(report, null, 2))}
            className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-800 hover:bg-slate-50 whitespace-nowrap shrink-0"
          >
            {copiedId === 'json-full' ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-700" />
                JSON скопирован
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-slate-500" />
                Копировать JSON
              </>
            )}
          </button>
        </div>

        <pre className="max-h-80 overflow-auto p-4 rounded-lg bg-slate-950 text-slate-100 text-xs font-mono leading-relaxed">
          <code>{JSON.stringify(report, null, 2)}</code>
        </pre>
      </section>
    </div>
  );
}
