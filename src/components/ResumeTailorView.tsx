import { useState } from 'react';
import { FileText, Copy, Check, ArrowRight } from 'lucide-react';
import type { CandidateProfile, RawVacancy, ResumeDraftResult } from '../types';

interface ResumeTailorViewProps {
  rawVacancies: RawVacancy[];
  candidates: CandidateProfile[];
  provider: 'rules' | 'ollama' | 'gigachat';
}

export function ResumeTailorView({
  rawVacancies,
  candidates,
  provider,
}: ResumeTailorViewProps) {
  const [selectedVacancyId, setSelectedVacancyId] = useState<string>(
    String(rawVacancies[0]?.id ?? ''),
  );
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>(
    candidates[0]?.id ?? '',
  );
  const [draft, setDraft] = useState<ResumeDraftResult | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const selectedCandidate =
    candidates.find((c) => c.id === selectedCandidateId) ?? candidates[0];
  const selectedVacancy =
    rawVacancies.find((v) => String(v.id) === selectedVacancyId) ??
    rawVacancies[0];

  const handleGenerate = async () => {
    if (!selectedVacancy || !selectedCandidate) return;
    setIsGenerating(true);
    setError(null);
    try {
      const resp = await fetch('/api/tailor-resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vacancy: selectedVacancy,
          candidate: selectedCandidate,
          provider,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || 'Не удалось сформировать черновик резюме.');
      }
      setDraft(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка генерации.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyMarkdown = async () => {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(draft.draft_markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="pb-5 border-b border-slate-200">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Дополнительный сценарий: черновик резюме под вакансию
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Подбирает релевантные навыки и опыт соискателя под выбранную вакансию региона 39. Все факты берутся строго из исходного обезличенного резюме без выдумывания.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Left: Controls */}
        <div className="xl:col-span-5 bg-white border border-slate-200 rounded-xl p-6 space-y-5">
          <div>
            <label
              htmlFor="resume-vacancy-select"
              className="block text-xs font-semibold text-slate-700 mb-1.5"
            >
              1. Выберите вакансию региона 39
            </label>
            <select
              id="resume-vacancy-select"
              value={selectedVacancyId}
              onChange={(e) => setSelectedVacancyId(e.target.value)}
              className="w-full h-10 px-3 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-700"
            >
              {rawVacancies.map((v) => (
                <option key={String(v.id)} value={String(v.id)}>
                  {String(v.id)} — {v['job-name'] || 'Без названия'}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="resume-candidate-select"
              className="block text-xs font-semibold text-slate-700 mb-1.5"
            >
              2. Выберите обезличенное резюме соискателя
            </label>
            <select
              id="resume-candidate-select"
              value={selectedCandidateId}
              onChange={(e) => setSelectedCandidateId(e.target.value)}
              className="w-full h-10 px-3 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-700"
            >
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name} ({c.target_role})
                </option>
              ))}
            </select>
          </div>

          {selectedCandidate && (
            <div className="pt-4 border-t border-slate-200 space-y-2 text-xs text-slate-600">
              <div className="font-semibold text-slate-900">Исходные данные резюме</div>
              <div>
                <span className="text-slate-500">Образование: </span>
                {selectedCandidate.education}
              </div>
              <div>
                <span className="text-slate-500">Навыки: </span>
                {selectedCandidate.skills.join(' · ')}
              </div>
            </div>
          )}

          <button
            type="button"
            disabled={isGenerating || !selectedVacancy || !selectedCandidate}
            onClick={handleGenerate}
            className="w-full inline-flex items-center justify-center gap-2 h-10 px-4 rounded-lg bg-blue-700 text-white text-sm font-semibold hover:bg-blue-800 disabled:opacity-50 transition-colors focus-visible:outline-2 focus-visible:outline-blue-700"
          >
            <FileText className="w-4 h-4" />
            {isGenerating ? 'Формируем черновик...' : 'Сформировать черновик резюме'}
            <ArrowRight className="w-4 h-4" />
          </button>

          {error && (
            <div role="alert" className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
              {error}
            </div>
          )}
        </div>

        {/* Right: Output */}
        <div className="xl:col-span-7 bg-white border border-slate-200 rounded-xl p-6">
          {!draft ? (
            <div className="py-12 text-center space-y-2">
              <FileText className="w-8 h-8 text-slate-300 mx-auto" />
              <div className="text-sm font-semibold text-slate-800">
                Черновик ещё не сформирован
              </div>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Выберите вакансию и профиль соискателя слева и нажмите «Сформировать черновик резюме», чтобы запустить Python-модуль <code className="font-mono">backend/resume_tailor.py</code>.
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              <div className="flex flex-wrap items-start justify-between gap-3 pb-4 border-b border-slate-200">
                <div>
                  <div className="text-xs font-mono text-slate-500">
                    {draft.vacancy_id} · {draft.candidate_id}
                  </div>
                  <h2 className="mt-1 text-lg font-bold text-slate-900">
                    {draft.candidate_name} → {draft.vacancy_title}
                  </h2>
                </div>

                <button
                  type="button"
                  onClick={handleCopyMarkdown}
                  className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-800 hover:bg-slate-50 whitespace-nowrap shrink-0"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-700" />
                      Markdown скопирован
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-slate-500" />
                      Копировать Markdown
                    </>
                  )}
                </button>
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-500">Краткое резюме</h3>
                <p className="text-sm text-slate-800 leading-relaxed">{draft.summary}</p>
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-500">
                  Совпавшие навыки (подтверждены исходным резюме)
                </h3>
                <p className="text-sm font-medium text-slate-900">
                  {draft.matched_skills.join(' · ')}
                </p>
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-500">Опыт работы</h3>
                <div className="space-y-3">
                  {draft.highlighted_experience.map((exp, idx) => (
                    <div key={idx} className="text-sm text-slate-800">
                      <div className="font-semibold text-slate-900">
                        {exp.role} — {exp.organization}{' '}
                        <span className="font-normal text-slate-500">({exp.period})</span>
                      </div>
                      <ul className="mt-1 list-disc list-inside text-xs text-slate-600 space-y-1">
                        {exp.achievements.map((a, i) => (
                          <li key={i}>{a}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2 pt-3 border-t border-slate-200">
                <h3 className="text-xs font-semibold text-slate-500">
                  На что обратить внимание при отклике
                </h3>
                <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
                  {draft.honest_gaps_and_questions.map((gap, i) => (
                    <li key={i}>{gap}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
