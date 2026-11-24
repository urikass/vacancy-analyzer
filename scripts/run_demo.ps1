<#
.SYNOPSIS
  Сценарий демонстрации сервиса «Прозрачная вакансия» (Регион 39) в Windows PowerShell.
  Подходит для проверки жюри и записи 3-минутного видео.
#>

$ErrorActionPreference = "Stop"

Write-Host "=== 1. Запуск автотестов Python ===" -ForegroundColor Cyan
python -m unittest discover -s backend/tests -v

Write-Host "`n=== 2. Проверочный режим (локальный JSON без запросов к порталу) ===" -ForegroundColor Cyan
# Для запуска с локальной ИИ-моделью Ollama (бесплатно, без аккаунта):
#   $env:LLM_PROVIDER="ollama"
#   $env:OLLAMA_MODEL="qwen2.5:7b"
# Для запуска с облачным GigaChat API:
#   $env:LLM_PROVIDER="gigachat"
#   (ключ GIGACHAT_AUTH_KEY берётся из локального файла .env)
python -m backend.cli check --input sample_data/demo_vacancies.json --output output/sample_report.json

Write-Host "`n=== 3. Фрагмент сформированного JSON-отчёта ===" -ForegroundColor Cyan
Get-Content output/sample_report.json -Encoding UTF8 | Select-Object -First 45

Write-Host "`n=== 4. Рабочий режим (ручной запуск API региона 39, минимум 2 страницы) ===" -ForegroundColor Cyan
python -m backend.cli fetch --max-vacancies 6 --page-size 3 --output output/latest_report.json

Write-Host "`n=== 5. Дополнительный сценарий: черновик резюме под вакансию DEMO-39-001 ===" -ForegroundColor Cyan
python -m backend.cli resume --input sample_data/demo_vacancies.json --vacancy-id DEMO-39-001 --resume sample_data/sample_resumes.json --candidate-id RESUME-001 --output output/resume_draft.json
Get-Content output/resume_draft.json -Encoding UTF8 | Select-Object -First 30
