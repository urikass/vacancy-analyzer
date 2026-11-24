"""Планировщик периодического сбора и анализа вакансий региона 39."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from backend.analyzer import run_working_mode
from backend.config import AppConfig


def run_scheduler_loop(
    config: AppConfig,
    interval_minutes: int | None = None,
    output_path: str | Path | None = None,
    max_runs: int | None = None,
    provider_override: str | None = None,
) -> None:
    """
    Запускает рабочий режим по расписанию (без ручного копирования текста).
    При недоступности API логирует ошибку и сохраняет последний успешный отчёт.
    """
    step_minutes = max(1, interval_minutes or config.schedule_interval_minutes)
    run_count = 0

    print(
        f"[SCHEDULER] Старт автоматического сбора. Интервал: каждые {step_minutes} мин. "
        f"Источник: {config.api_url} (макс. вакансий: {config.max_vacancies})."
    )

    try:
        while True:
            run_count += 1
            started = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"[SCHEDULER] Запуск #{run_count} в {started}...")
            result = run_working_mode(
                config=config,
                output_path=output_path,
                provider_override=provider_override,
            )
            print(f"[SCHEDULER] Результат #{run_count}: {result['status']} — {result['message']}")

            if max_runs is not None and run_count >= max_runs:
                print(f"[SCHEDULER] Достигнут лимит запусков ({max_runs}). Завершение.")
                break

            print(f"[SCHEDULER] Следующий запуск через {step_minutes} мин. (Ctrl+C для остановки)")
            time.sleep(step_minutes * 60)
    except KeyboardInterrupt:
        print("\n[SCHEDULER] Остановлено пользователем.")
