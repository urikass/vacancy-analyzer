"""
Точка входа CLI и локального HTTP-сервера сервиса «Прозрачная вакансия» (Регион 39).

Примеры запуска в PowerShell:
  python -m backend.cli check --input sample_data/demo_vacancies.json --output output/sample_report.json
  python -m backend.cli fetch --max-vacancies 40 --page-size 20 --output output/latest_report.json
  python -m backend.cli schedule --interval-minutes 60
  python -m backend.cli resume --input sample_data/demo_vacancies.json --vacancy-id DEMO-39-001 --resume sample_data/sample_resumes.json --candidate-id RESUME-001
  python -m backend.cli serve --port 8000
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from backend.analyzer import (
    analyze_vacancies,
    run_verification_mode,
    run_working_mode,
)
from backend.config import AppConfig
from backend.resume_tailor import generate_resume_draft
from backend.scheduler import run_scheduler_loop
from backend.trudvsem_client import extract_vacancies_from_payload, load_vacancies_from_file


def _cmd_check(args: argparse.Namespace, config: AppConfig) -> int:
    if args.stdin:
        raw_payload = json.loads(sys.stdin.read())
        vacancies = extract_vacancies_from_payload(raw_payload)
        report = analyze_vacancies(
            raw_vacancies=vacancies,
            config=config,
            mode="verification",
            source="stdin",
            pages_fetched=0,
            provider_override=args.provider,
            strict_ai=args.strict_ai,
        )
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0

    report = run_verification_mode(
        input_path=args.input,
        output_path=args.output,
        config=config,
        provider_override=args.provider,
        strict_ai=args.strict_ai,
    )
    if args.stdout:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(
            f"[OK] Проверочный режим завершён. Вакансий: {report.total_vacancies}, "
            f"с замечаниями: {report.vacancies_with_issues}, всего замечаний: {report.total_issues}."
        )
        print(f"[OK] ИИ: {report.ai_note}")
        print(f"[OK] Отчёт сохранён в: {args.output}")
    return 0


def _cmd_fetch(args: argparse.Namespace, config: AppConfig) -> int:
    result = run_working_mode(
        config=config,
        output_path=args.output or config.last_report_path,
        api_url=args.url or config.api_url,
        max_vacancies=args.max_vacancies if args.max_vacancies is not None else config.max_vacancies,
        page_size=args.page_size if args.page_size is not None else config.page_size,
        provider_override=args.provider,
    )
    if args.stdout:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        prefix = "[OK]" if result["status"] == "ok" else "[ERROR]"
        print(f"{prefix} {result['message']}")
        if result.get("report_path"):
            print(f"{prefix} Файл отчёта: {result['report_path']}")
    return 0 if result["status"] == "ok" else 1


def _cmd_schedule(args: argparse.Namespace, config: AppConfig) -> int:
    run_scheduler_loop(
        config=config,
        interval_minutes=args.interval_minutes,
        output_path=args.output or config.last_report_path,
        max_runs=args.max_runs,
        provider_override=args.provider,
    )
    return 0


def _cmd_resume(args: argparse.Namespace, config: AppConfig) -> int:
    if args.stdin:
        body = json.loads(sys.stdin.read())
        vacancy = body.get("vacancy")
        candidate = body.get("candidate")
        if not isinstance(vacancy, dict) or not isinstance(candidate, dict):
            raise ValueError("Ожидается JSON с объектами 'vacancy' и 'candidate'.")
    else:
        vacancies = load_vacancies_from_file(args.input)
        vacancy = next(
            (v for v in vacancies if str(v.get("id")) == args.vacancy_id),
            vacancies[0] if vacancies else None,
        )
        if vacancy is None:
            raise ValueError(f"Вакансия {args.vacancy_id} не найдена в {args.input}.")
        resumes_payload = json.loads(Path(args.resume).read_text(encoding="utf-8-sig"))
        candidates = resumes_payload.get("candidates") if isinstance(resumes_payload, dict) else resumes_payload
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Файл резюме не содержит кандидатов.")
        candidate = next(
            (c for c in candidates if str(c.get("id")) == args.candidate_id),
            candidates[0],
        )

    result = generate_resume_draft(
        raw_vacancy=vacancy,
        candidate=candidate,
        config=config,
        provider_override=args.provider,
    )
    output_json = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_json, encoding="utf-8")
    if args.stdout or args.stdin or not args.output:
        print(output_json)
    else:
        print(f"[OK] Черновик резюме для «{result.vacancy_title}» сохранён в: {args.output}")
    return 0


def _cmd_serve(args: argparse.Namespace, config: AppConfig) -> int:
    """Локальный HTTP API на стандартной библиотеке Python (для подключения фронтенда)."""

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: Any) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api/health":
                self._send_json(200, {"status": "ok", "provider": config.llm_provider})
                return
            self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            if length > 5 * 1024 * 1024:
                self._send_json(413, {"error": "Payload too large"})
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON"})
                return

            if self.path == "/api/check":
                try:
                    vacancies = extract_vacancies_from_payload(body.get("payload", body))
                    provider = body.get("provider") if isinstance(body, dict) else None
                    report = analyze_vacancies(
                        raw_vacancies=vacancies,
                        config=config,
                        mode="verification",
                        source="api-upload",
                        provider_override=provider,
                    )
                    self._send_json(200, report.to_dict())
                except Exception as exc:  # noqa: BLE001
                    self._send_json(400, {"error": str(exc)})
                return

            if self.path == "/api/fetch":
                result = run_working_mode(
                    config=config,
                    api_url=body.get("url") or config.api_url,
                    max_vacancies=int(body.get("max_vacancies") or config.max_vacancies),
                    page_size=int(body.get("page_size") or config.page_size),
                    provider_override=body.get("provider"),
                )
                self._send_json(200 if result["status"] == "ok" else 502, result)
                return

            if self.path == "/api/resume":
                try:
                    draft = generate_resume_draft(
                        raw_vacancy=body["vacancy"],
                        candidate=body["candidate"],
                        config=config,
                        provider_override=body.get("provider"),
                    )
                    self._send_json(200, draft.to_dict())
                except Exception as exc:  # noqa: BLE001
                    self._send_json(400, {"error": str(exc)})
                return

            self._send_json(404, {"error": "Not found"})

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[SERVER] Python API запущен на http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Остановлен.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.cli",
        description="Прозрачная вакансия — анализатор вакансий региона 39 (КАНТКОД).",
    )
    parser.add_argument("--env-file", default=None, help="Путь к .env файлу (по умолчанию ./.env)")

    sub = parser.add_subparsers(dest="command", required=True)

    # 1. Проверочный режим
    p_check = sub.add_parser("check", help="Проверочный режим: анализ локального JSON без запросов к порталу.")
    p_check.add_argument("--input", "-i", default="sample_data/demo_vacancies.json", help="Путь к входному JSON.")
    p_check.add_argument("--output", "-o", default="output/sample_report.json", help="Путь сохранения JSON-отчёта.")
    p_check.add_argument("--provider", choices=["gigachat", "ollama", "rules"], default=None, help="Переопределить ИИ-провайдер.")
    p_check.add_argument("--strict-ai", action="store_true", help="Завершать с ошибкой, если ИИ недоступен.")
    p_check.add_argument("--stdin", action="store_true", help="Читать входной JSON из stdin и печатать отчёт в stdout.")
    p_check.add_argument("--stdout", action="store_true", help="Дополнительно вывести итоговый JSON в stdout.")

    # 2. Рабочий режим (ручной запуск)
    p_fetch = sub.add_parser("fetch", help="Рабочий режим (ручной запуск): загрузка с API региона 39 и сохранение отчёта.")
    p_fetch.add_argument("--url", default=None, help="URL источника API «Работа в России».")
    p_fetch.add_argument("--max-vacancies", type=int, default=None, help="Максимальное число вакансий.")
    p_fetch.add_argument("--page-size", type=int, default=None, help="Размер одной страницы API.")
    p_fetch.add_argument("--output", "-o", default=None, help="Путь сохранения отчёта.")
    p_fetch.add_argument("--provider", choices=["gigachat", "ollama", "rules"], default=None, help="Переопределить ИИ-провайдер.")
    p_fetch.add_argument("--stdout", action="store_true", help="Вывести результат JSON в stdout.")

    # 3. Рабочий режим по расписанию
    p_sched = sub.add_parser("schedule", help="Рабочий режим: автоматический запуск по расписанию.")
    p_sched.add_argument("--interval-minutes", type=int, default=None, help="Интервал запуска в минутах.")
    p_sched.add_argument("--max-runs", type=int, default=None, help="Ограничение числа циклов (для проверки).")
    p_sched.add_argument("--output", "-o", default=None, help="Путь сохранения отчёта.")
    p_sched.add_argument("--provider", choices=["gigachat", "ollama", "rules"], default=None, help="Переопределить ИИ-провайдер.")

    # 4. Дополнительный сценарий (черновик резюме)
    p_res = sub.add_parser("resume", help="Доп. сценарий: подготовка черновика резюме под вакансию региона 39.")
    p_res.add_argument("--input", "-i", default="sample_data/demo_vacancies.json", help="JSON с вакансиями.")
    p_res.add_argument("--vacancy-id", default="DEMO-39-001", help="ID выбранной вакансии.")
    p_res.add_argument("--resume", default="sample_data/sample_resumes.json", help="JSON с резюме соискателей.")
    p_res.add_argument("--candidate-id", default="RESUME-001", help="ID профиля соискателя.")
    p_res.add_argument("--output", "-o", default="output/resume_draft.json", help="Путь сохранения черновика.")
    p_res.add_argument("--provider", choices=["gigachat", "ollama", "rules"], default=None, help="Переопределить ИИ-провайдер.")
    p_res.add_argument("--stdin", action="store_true", help="Читать {vacancy, candidate} из stdin.")
    p_res.add_argument("--stdout", action="store_true", help="Вывести результат JSON в stdout.")

    # 5. Локальный Python HTTP-сервер
    p_serve = sub.add_parser("serve", help="Запуск локального HTTP API на Python.")
    p_serve.add_argument("--host", default="127.0.0.1", help="Хост (по умолчанию 127.0.0.1).")
    p_serve.add_argument("--port", type=int, default=8000, help="Порт (по умолчанию 8000).")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig.from_env(args.env_file)

    if args.command == "check":
        return _cmd_check(args, config)
    if args.command == "fetch":
        return _cmd_fetch(args, config)
    if args.command == "schedule":
        return _cmd_schedule(args, config)
    if args.command == "resume":
        return _cmd_resume(args, config)
    if args.command == "serve":
        return _cmd_serve(args, config)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
