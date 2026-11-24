import {
  FileCheck2,
  Globe,
  FileUser,
  Terminal,
  Menu,
  X,
} from 'lucide-react';
import type { ActiveTab } from '../types';

interface SidebarProps {
  activeTab: ActiveTab;
  onSelectTab: (tab: ActiveTab) => void;
  totalVacancies: number;
  totalIssues: number;
  mobileOpen: boolean;
  onToggleMobile: () => void;
}

const NAV_ITEMS: Array<{
  id: ActiveTab;
  label: string;
  caption: string;
  icon: typeof FileCheck2;
}> = [
  {
    id: 'report',
    label: 'Проверка отчёта',
    caption: 'Проверочный режим (JSON)',
    icon: FileCheck2,
  },
  {
    id: 'live',
    label: 'Сбор с API',
    caption: 'Регион 39 · расписание',
    icon: Globe,
  },
  {
    id: 'resume',
    label: 'Черновик резюме',
    caption: 'Дополнительный сценарий',
    icon: FileUser,
  },
  {
    id: 'guide',
    label: 'Запуск и сдача',
    caption: 'PowerShell · GigaChat · Ollama',
    icon: Terminal,
  },
];

export function Sidebar({
  activeTab,
  onSelectTab,
  totalVacancies,
  totalIssues,
  mobileOpen,
  onToggleMobile,
}: SidebarProps) {
  const navContent = (
    <div className="flex h-full flex-col bg-white border-r border-slate-200">
      <div className="px-6 py-5 border-b border-slate-200 flex items-center justify-between">
        <span className="text-base font-bold tracking-tight text-slate-900 whitespace-nowrap">
          Прозрачная вакансия
        </span>
        <button
          type="button"
          onClick={onToggleMobile}
          aria-label="Закрыть меню"
          className="lg:hidden p-1.5 text-slate-500 hover:text-slate-900 rounded-md focus-visible:outline-2 focus-visible:outline-blue-700"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav aria-label="Разделы рабочей области" className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                onSelectTab(item.id);
                if (mobileOpen) onToggleMobile();
              }}
              aria-current={isActive ? 'page' : undefined}
              className={`w-full text-left flex items-start gap-3 px-3 py-2.5 rounded-lg transition-colors focus-visible:outline-2 focus-visible:outline-blue-700 ${
                isActive
                  ? 'bg-slate-900 text-white'
                  : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <Icon
                className={`w-4 h-4 mt-0.5 shrink-0 ${
                  isActive ? 'text-blue-300' : 'text-slate-400'
                }`}
              />
              <span className="min-w-0">
                <span className="block text-sm font-semibold leading-tight whitespace-nowrap truncate">
                  {item.label}
                </span>
                <span
                  className={`block text-xs mt-0.5 truncate ${
                    isActive ? 'text-slate-300' : 'text-slate-500'
                  }`}
                >
                  {item.caption}
                </span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="px-6 py-4 border-t border-slate-200 text-xs text-slate-500 space-y-1">
        <div className="font-medium text-slate-700">Калининградская область · 39</div>
        <div className="tabular-nums">
          Вакансий: {totalVacancies} · Замечаний: {totalIssues}
        </div>
        <div className="text-slate-400">Python 3 · Работа в России</div>
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden lg:block w-64 shrink-0 h-screen sticky top-0">
        {navContent}
      </aside>

      {/* Mobile drawer trigger helper */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden flex">
          <div className="w-72 max-w-[85vw] h-full shadow-xl">{navContent}</div>
          <button
            type="button"
            aria-label="Скрыть меню"
            onClick={onToggleMobile}
            className="flex-1 bg-slate-900/30"
          />
        </div>
      )}
    </>
  );
}

export function MobileMenuButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Открыть навигацию"
      className="lg:hidden inline-flex items-center justify-center p-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-blue-700"
    >
      <Menu className="w-5 h-5" />
    </button>
  );
}
