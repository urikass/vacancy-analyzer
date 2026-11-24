<#
.SYNOPSIS
  Регистрирует задачу Windows Task Scheduler для автоматического запуска рабочего режима по расписанию.
#>

param(
    [string]$ProjectDir = (Get-Location).Path,
    [int]$IntervalMinutes = 60
)

$Action = New-ScheduledTaskAction -Execute "python" `
    -Argument "-m backend.cli fetch --max-vacancies 40 --page-size 20 --output output/latest_report.json" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

Register-ScheduledTask -TaskName "KantKod_TransparentVacancy_Region39" `
    -Action $Action `
    -Trigger $Trigger `
    -Description "Автоматический сбор и анализ вакансий региона 39 с портала Работа в России" `
    -Force

Write-Host "Задача планировщика KantKod_TransparentVacancy_Region39 зарегистрирована (каждые $IntervalMinutes мин)." -ForegroundColor Green
