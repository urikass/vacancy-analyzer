import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import express from 'express';
import { createServer as createViteServer } from 'vite';
import 'dotenv/config';

const ROOT_DIR = process.cwd();
const PORT = Number(process.env.PORT) || 3000;
const ALLOWED_PROVIDERS = new Set(['rules', 'ollama', 'gigachat']);
const PYTHON_BIN = process.platform === 'win32' ? 'python' : 'python3';

function runPythonCli(args: string[], stdinPayload?: string): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_BIN, ['-m', 'backend.cli', ...args], {
      cwd: ROOT_DIR,
      shell: false,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });

    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      proc.kill('SIGTERM');
      reject(new Error('Превышено время ожидания выполнения Python-анализатора (240 с).'));
    }, 240_000);

    proc.stdout.on('data', (chunk: Buffer) => {
      stdout += chunk.toString('utf-8');
    });
    proc.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString('utf-8');
    });
    proc.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
    proc.on('close', (code) => {
      clearTimeout(timer);
      resolve({ code: code ?? 1, stdout, stderr });
    });

    if (stdinPayload !== undefined) {
      proc.stdin.write(stdinPayload, 'utf-8');
      proc.stdin.end();
    }
  });
}

function validateAllowedApiUrl(rawUrl: string): string {
  let parsed: URL;
  try {
    parsed = new URL(rawUrl.trim());
  } catch {
    throw new Error('Некорректный формат URL источника.');
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error('Разрешены только протоколы http и https.');
  }
  if (parsed.hostname.toLowerCase() !== 'opendata.trudvsem.ru') {
    throw new Error('В целях безопасности разрешён только официальный хост opendata.trudvsem.ru.');
  }
  return parsed.toString();
}

async function startServer() {
  const app = express();
  app.use(express.json({ limit: '5mb' }));

  app.get('/api/initial-data', async (_req, res) => {
    try {
      const [reportRaw, demoRaw, resumesRaw] = await Promise.all([
        fs.readFile(path.join(ROOT_DIR, 'output', 'sample_report.json'), 'utf-8'),
        fs.readFile(path.join(ROOT_DIR, 'sample_data', 'demo_vacancies.json'), 'utf-8'),
        fs.readFile(path.join(ROOT_DIR, 'sample_data', 'sample_resumes.json'), 'utf-8'),
      ]);

      const demoParsed = JSON.parse(demoRaw);
      const rawVacancies = (demoParsed?.results?.vacancies ?? []).map(
        (entry: { vacancy?: Record<string, unknown> }) => entry.vacancy ?? entry,
      );

      res.json({
        report: JSON.parse(reportRaw),
        rawVacancies,
        candidates: JSON.parse(resumesRaw)?.candidates ?? [],
        envStatus: {
          gigachatConfigured: Boolean(process.env.GIGACHAT_AUTH_KEY?.trim()),
          ollamaUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434',
          ollamaModel: process.env.OLLAMA_MODEL || 'qwen2.5:7b',
          defaultApiUrl: process.env.TRUDVSEM_API_URL || 'http://opendata.trudvsem.ru/api/v1/vacancies/region/39',
        },
      });
    } catch (err) {
      res.status(500).json({
        error: err instanceof Error ? err.message : 'Не удалось загрузить учебные данные.',
      });
    }
  });

  app.post('/api/analyze-json', async (req, res) => {
    try {
      const { payload, provider } = req.body ?? {};
      if (!payload || typeof payload !== 'object') {
        res.status(400).json({ error: 'Передайте корректный JSON в формате ответа API «Работа в России».' });
        return;
      }

      const safeProvider =
        typeof provider === 'string' && ALLOWED_PROVIDERS.has(provider.toLowerCase())
          ? provider.toLowerCase()
          : 'rules';

      const result = await runPythonCli(
        ['check', '--stdin', '--provider', safeProvider],
        JSON.stringify(payload),
      );

      if (result.code !== 0) {
        res.status(400).json({
          error: result.stderr.trim() || 'Python-анализатор вернул ошибку при разборе JSON.',
        });
        return;
      }

      const report = JSON.parse(result.stdout);
      const rawList = Array.isArray(payload)
        ? payload
        : payload?.results?.vacancies ?? payload?.vacancies ?? [];
      const rawVacancies = Array.isArray(rawList)
        ? rawList.map((entry: { vacancy?: Record<string, unknown> }) => entry?.vacancy ?? entry)
        : [];

      res.json({ report, rawVacancies });
    } catch (err) {
      res.status(500).json({
        error: err instanceof Error ? err.message : 'Ошибка выполнения анализа.',
      });
    }
  });

  app.post('/api/fetch-live', async (req, res) => {
    try {
      const { url, maxVacancies, pageSize, provider } = req.body ?? {};
      const safeUrl = validateAllowedApiUrl(
        typeof url === 'string' && url.trim()
          ? url
          : 'http://opendata.trudvsem.ru/api/v1/vacancies/region/39',
      );
      const safeMax = Math.max(2, Math.min(100, Number(maxVacancies) || 20));
      const safePage = Math.max(1, Math.min(50, Number(pageSize) || 10));
      const safeProvider =
        typeof provider === 'string' && ALLOWED_PROVIDERS.has(provider.toLowerCase())
          ? provider.toLowerCase()
          : 'rules';

      const args = [
        'fetch',
        '--url',
        safeUrl,
        '--max-vacancies',
        String(safeMax),
        '--page-size',
        String(safePage),
        '--provider',
        safeProvider,
        '--output',
        'output/latest_report.json',
        '--stdout',
      ];

      const result = await runPythonCli(args);
      if (!result.stdout.trim()) {
        res.status(502).json({
          status: 'error',
          error: result.stderr.trim() || 'Не удалось получить ответ от API «Работа в России».',
          preserved_last_report: false,
        });
        return;
      }

      const parsed = JSON.parse(result.stdout);
      res.status(parsed.status === 'ok' ? 200 : 502).json(parsed);
    } catch (err) {
      res.status(400).json({
        status: 'error',
        error: err instanceof Error ? err.message : 'Ошибка запуска рабочего режима.',
      });
    }
  });

  app.post('/api/tailor-resume', async (req, res) => {
    try {
      const { vacancy, candidate, provider } = req.body ?? {};
      if (!vacancy || typeof vacancy !== 'object' || !candidate || typeof candidate !== 'object') {
        res.status(400).json({ error: 'Нужно выбрать вакансию и профиль соискателя.' });
        return;
      }

      const safeProvider =
        typeof provider === 'string' && ALLOWED_PROVIDERS.has(provider.toLowerCase())
          ? provider.toLowerCase()
          : 'rules';

      const result = await runPythonCli(
        ['resume', '--stdin', '--provider', safeProvider],
        JSON.stringify({ vacancy, candidate }),
      );

      if (result.code !== 0) {
        res.status(400).json({
          error: result.stderr.trim() || 'Не удалось сформировать черновик резюме.',
        });
        return;
      }

      res.json(JSON.parse(result.stdout));
    } catch (err) {
      res.status(500).json({
        error: err instanceof Error ? err.message : 'Ошибка дополнительного сценария.',
      });
    }
  });

  const isProd = process.env.NODE_ENV === 'production';
  if (isProd) {
    const distDir = path.join(ROOT_DIR, 'dist');
    app.use(express.static(distDir));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distDir, 'index.html'));
    });
  } else {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Transparent Vacancy workbench listening on http://localhost:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
