# Прозрачная вакансия — Регион 39 (КАНТКОД)

Прототип сервиса на **Python**, который автоматически получает вакансии Калининградской области (регион 39) с портала **«Работа в России»**, оценивает понятность условий работы с помощью гибридного анализатора (**детерминированные правила + ИИ**) и формирует структурированный JSON-отчёт с конкретными рекомендациями для редактора вакансий.

**Точка входа (файл, с которого начинается обработка):** `backend/cli.py` (запуск командой `python -m backend.cli ...`).

---

## Состав команды и вклад участников

| Участник | Роль | Вклад в проект |
| --- | --- | --- |
| **Юрий** | Тимлид, Backend-разработчик | Архитектура Python-бэкенда (`backend/`), клиент API «Работа в России» с пагинацией, гибридный анализатор (правила + GigaChat API + локальная Ollama), CLI для PowerShell, планировщик, автотесты (`unittest`), сборка `sample_report.json`. |
| **Доминикас** | Frontend-разработчик | Веб-интерфейс редактора вакансий (`src/`), фильтры замечаний, загрузка локального JSON, экран рабочего режима, интерфейс дополнительного сценария и интеграция с бэкендом. |
| **Илья** | UI/UX-дизайнер | Визуальная система дашборда «Прозрачная вакансия», карточка разбора замечаний (пропуск / неоднозначность / противоречие), читаемая типографика и структура экранов для редактора. |
| **Тимофей** | Дизайнер контента и видео | Сценарий, запись и монтаж 3-минутного демонстрационного видео с показом загрузки данных, шага ИИ, итогового отчёта и дополнительного сценария. |
| **Камилла** | Менеджер проекта | Координация команды и сроков сдачи, сверка всех критериев задания КАНТКОД, подготовка обезличенных примеров резюме, проверка комплектности README, репозитория и формы сдачи. |

---

## Архитектура и шаг использования ИИ

Обработка каждой вакансии проходит в три шага (`backend/analyzer.py`):

1. **Нормализация данных (`backend/rules.py` → `normalize_vacancy`)**: считываются одновременно структурированные поля API (`salary_min`, `salary_max`, `schedule`, `employment`, `requirement.education`, `requirement.experience`, `addresses`) и текстовые описания (`duty`, `requirements`, `requirement.qualification`). Если структурированное поле уже содержит конкретные данные, отсутствие их повторения в тексте проблемой не считается.
2. **Детерминированные проверки (`backend/rules.py` → `run_rule_checks`)**: проверяются 7 критериев задания (название должности, обязанности, требования, оплата, график, место работы, тип занятости), явные пропуски и противоречия между полями.
3. **ИИ-анализ (`backend/llm_clients.py` → `GigaChatClient` / `OllamaClient`)**: на этом шаге языковая модель получает структурированную вакансию и предварительный список замечаний, выявляет скрытые семантические неоднозначности и противоречия, предлагает конкретные формулировки вопросов работодателю. Выводы о нарушении закона и вымышленные факты программно отфильтровываются.

### Поддерживаемые ИИ-провайдеры

* **Локальный запуск через Ollama (бесплатно, без покупки аккаунта — рекомендовано для проверки жюри):**
  * Модель по умолчанию: `qwen2.5:7b` (можно заменить на любую русскоязычную модель Ollama, например `gemma3:4b` или `llama3.1:8b`).
  * Настраивается через `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://127.0.0.1:11434`, `OLLAMA_MODEL=qwen2.5:7b`.
* **Облачный GigaChat API (Сбер):**
  * Модель по умолчанию: `GigaChat` (доступен бесплатный стартовый пакет токенов на `developers.sber.ru`).
  * Настраивается через `LLM_PROVIDER=gigachat` и переменную окружения `GIGACHAT_AUTH_KEY` в локальном `.env` (ключи **не хранятся** в репозитории).
* **Режим правил (`LLM_PROVIDER=rules`):** для быстрых детерминированных автотестов без сети.

---

## Зависимости и настройка

* **Python 3.10+** (ядро CLI, клиент API, GigaChat OAuth/Chat, Ollama, планировщик и автотесты написаны на **стандартной библиотеке Python** — работают сразу без сборки сторонних пакетов).
* Опционально для веб-интерфейса: **Node.js 20+** (`npm install && npm run dev`).

### Настройка переменных окружения

Скопируйте `.env.example` в `.env` (файл `.env` добавлен в `.gitignore`, ключи хранятся вне репозитория):

```powershell
Copy-Item .env.example .env
```

Основные параметры `.env`:
* `TRUDVSEM_API_URL` — URL источника (по умолчанию `http://opendata.trudvsem.ru/api/v1/vacancies/region/39`).
* `MAX_VACANCIES` — максимальное число вакансий за прогон (по умолчанию `40`).
* `PAGE_SIZE` — размер одной страницы API (по умолчанию `20`; при лимите `>= 2` автоматически загружается минимум 2 страницы).
* `SCHEDULE_INTERVAL_MINUTES` / `SCHEDULE_CRON` — расписание автоматического сбора.
* `LLM_PROVIDER` — `ollama`, `gigachat` или `rules`.
* `GIGACHAT_AUTH_KEY` — ключ авторизации GigaChat (только в локальном `.env`).
* `OLLAMA_BASE_URL`, `OLLAMA_MODEL` — адрес и модель локальной Ollama.

---

## Команды запуска и проверки (Windows PowerShell)

### 1. Проверочный режим с ИИ без покупки аккаунта (локальная Ollama)

1. Установите [Ollama](https://ollama.com/) и скачайте модель:
   ```powershell
   ollama pull qwen2.5:7b
   ```
2. Запустите проверочный режим на учебном JSON (или на проверочном JSON жюри) **без обращений к порталу**:
   ```powershell
   $env:LLM_PROVIDER="ollama"
   $env:OLLAMA_MODEL="qwen2.5:7b"
   python -m backend.cli check --input sample_data/demo_vacancies.json --output output/sample_report.json
   ```

### 2. Проверочный режим через GigaChat API

Добавьте ваш `GIGACHAT_AUTH_KEY` в локальный `.env`, выставьте `LLM_PROVIDER=gigachat` и выполните:

```powershell
python -m backend.cli check --input sample_data/demo_vacancies.json --output output/sample_report.json --provider gigachat
```

### 3. Рабочий режим (ручной запуск и расписание)

Ручной запуск сбора с портала «Работа в России» (минимум 2 страницы; при недоступности API выводится ошибка, а предыдущий успешный отчёт сохраняется):

```powershell
python -m backend.cli fetch --max-vacancies 40 --page-size 20 --output output/latest_report.json
```

Запуск встроенного планировщика по расписанию:

```powershell
python -m backend.cli schedule --interval-minutes 60
```

Регистрация задачи в системном планировщике Windows (Task Scheduler) или cron (Linux/macOS):
* Windows: `.\scripts\register_task.ps1 -IntervalMinutes 60`
* Linux/macOS: шаблон в `config/schedule.cron`

### 4. Автотесты и единый демо-сценарий

```powershell
python -m unittest discover -s backend/tests -v
```

Запуск полного демо-сценария одной командой:

```powershell
.\scripts\run_demo.ps1
```

### 5. Веб-интерфейс редактора (опционально)

```powershell
npm install
npm run dev
# Откройте http://localhost:3000
```

---

## Формат JSON-отчёта (`output/sample_report.json`)

```json
{
  "meta": {
    "generated_at": "2026-11-24T12:00:00+00:00",
    "mode": "verification | working",
    "source": "sample_data/demo_vacancies.json",
    "ai_provider": "ollama | gigachat | rules",
    "ai_model": "qwen2.5:7b",
    "ai_applied": true,
    "ai_note": "Описание результата работы ИИ",
    "pages_fetched": 0,
    "total_vacancies": 10,
    "vacancies_with_issues": 6,
    "total_issues": 16
  },
  "vacancies": [
    {
      "vacancy_id": "DEMO-39-004",
      "vacancy_url": null,
      "job_name": "Оператор контактного центра",
      "company_name": "Учебная организация «Балтика»",
      "issues": [
        {
          "topic": "место работы",
          "issue_type": "contradiction",
          "source_field": "duty, requirement.qualification",
          "quote": "duty: \"...Работа полностью дистанционная...\" | requirement.qualification: \"Обязательное ежедневное присутствие в офисе...\"",
          "problem": "В описании обязанностей указана полностью дистанционная работа, а в требованиях — обязательное ежедневное присутствие в офисе.",
          "recommendation": "Уточните фактический формат работы (офис, гибрид или полностью удалённо) и уберите противоречащую формулировку.",
          "detected_by": "rules | ai | hybrid"
        }
      ]
    }
  ]
}
```

* Если по вакансии замечаний нет, поле `issues` содержит пустой массив `[]` (например, `DEMO-39-001`, `DEMO-39-005`, `DEMO-39-007`, `DEMO-39-009`).
* Для **пропуска** (`issue_type: "omission"`) поле `quote` всегда пустое `""`.
* Для **противоречия** (`issue_type: "contradiction"`) в `quote` приводятся **оба** исходных значения.
* При повторном запуске на неизменных данных для каждого `vacancy_id` сохраняется строго один результат.

---

## Дополнительный сценарий: черновик резюме под вакансию региона 39

* **Кому помогает:** соискателям Калининградской области и карьерным консультантам центров занятости.
* **Какие данные API использует:** `id`, `job-name`, `company.name`, `duty`, `requirements`, `requirement.education`, `requirement.experience`, `requirement.qualification`, `schedule`, `salary_min/max`.
* **Какой результат выдаёт:** структурированный JSON и Markdown-черновик резюме, адаптированный под выбранную вакансию. Опыт, навыки и образование берутся **строго из исходного обезличенного резюме** (`sample_data/sample_resumes.json`), а недостающие требования честно выносятся в список вопросов к работодателю.

Команда запуска в PowerShell:

```powershell
python -m backend.cli resume `
  --input sample_data/demo_vacancies.json `
  --vacancy-id DEMO-39-001 `
  --resume sample_data/sample_resumes.json `
  --candidate-id RESUME-001 `
  --output output/resume_draft.json
```
