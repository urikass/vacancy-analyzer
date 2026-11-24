export type IssueType = 'omission' | 'ambiguity' | 'contradiction';

export interface Issue {
  topic: string;
  issue_type: IssueType;
  source_field: string;
  quote: string;
  problem: string;
  recommendation: string;
  detected_by: 'rules' | 'ai' | 'hybrid';
}

export interface VacancyReportItem {
  vacancy_id: string;
  vacancy_url: string | null;
  job_name: string;
  company_name: string;
  issues: Issue[];
}

export interface ReportMeta {
  generated_at: string;
  mode: 'verification' | 'working';
  source: string;
  ai_provider: string;
  ai_model: string | null;
  ai_applied: boolean;
  ai_note: string;
  pages_fetched: number;
  total_vacancies: number;
  vacancies_with_issues: number;
  total_issues: number;
}

export interface AnalysisReport {
  meta: ReportMeta;
  vacancies: VacancyReportItem[];
}

export interface RawVacancy {
  id: string;
  'job-name'?: string;
  salary_min?: number;
  salary_max?: number;
  currency?: string;
  employment?: string;
  schedule?: string;
  duty?: string;
  requirements?: string;
  requirement?: {
    education?: string;
    experience?: number;
    qualification?: string;
  };
  company?: {
    name?: string;
  };
  addresses?: {
    address?: Array<{ location?: string }>;
  };
  vac_url?: string;
  url?: string;
  [key: string]: unknown;
}

export interface CandidateExperience {
  role: string;
  organization: string;
  period: string;
  achievements: string[];
}

export interface CandidateProfile {
  id: string;
  full_name: string;
  target_role: string;
  location: string;
  education: string;
  experience_years: number;
  experience: CandidateExperience[];
  skills: string[];
  summary: string;
}

export interface ResumeDraftResult {
  vacancy_id: string;
  vacancy_title: string;
  company_name: string;
  candidate_id: string;
  candidate_name: string;
  ai_provider: string;
  ai_used: boolean;
  summary: string;
  matched_skills: string[];
  highlighted_experience: CandidateExperience[];
  education: string;
  honest_gaps_and_questions: string[];
  draft_markdown: string;
}

export interface EnvStatus {
  gigachatConfigured: boolean;
  ollamaUrl: string;
  ollamaModel: string;
  defaultApiUrl: string;
}

export type FilterKey =
  | 'all'
  | 'with_issues'
  | 'contradiction'
  | 'omission'
  | 'ambiguity'
  | 'clean';

export type ActiveTab = 'report' | 'live' | 'resume' | 'guide';
