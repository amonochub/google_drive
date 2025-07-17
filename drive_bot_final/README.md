# Drive Bot Final

Бот для работы с Google Drive, OCR и AI через Telegram.

---

## Новые возможности
- **Валидация файлов**: проверка расширения, размера, имени (опасные и неподдерживаемые файлы блокируются).
- **Rate limiting**: ограничение количества запросов в минуту на пользователя.
- **Structured logging**: все логи в формате JSON для удобства мониторинга и аудита.
- **Мониторинг**: middleware для сбора статистики, логирования медленных и ошибочных запросов.
- **Fuzzy-поиск папок**: быстрый поиск похожих папок по имени файла.
- **Retry и устойчивость**: автоматические повторы при ошибках Google Drive API.

---

## Архитектура

- **Telegram-бот** (aiogram): принимает команды и документы от пользователей.
- **Google Drive API**: загрузка, поиск и организация файлов/папок через сервисный аккаунт.
- **OCR**: извлечение текста из PDF (PyMuPDF, pytesseract, Pillow).
- **AI-анализ**: базовый анализ текста (SimpleRegexAnalyzer, можно расширять).
- **Асинхронность**: все основные операции выполняются асинхронно.
- **Celery**: для фоновых задач (например, тяжелый OCR/AI-анализ).
- **Redis**: брокер для Celery и хранения сессий.
- **PostgreSQL** (опционально): для хранения истории, логов и т.д.
- **Prometheus**: мониторинг метрик (опционально).

### Основные директории
- `handlers/` — обработчики Telegram-команд и логики работы с Google Drive.
- `services/` — сервисы для OCR, AI и других вспомогательных задач.
- `tasks/` — задачи Celery.
- `utils/` — вспомогательные утилиты (валидация, rate limiting, меню, роутинг и т.д.).
- `middleware/` — middleware для мониторинга и логирования.
- `config.py` — все настройки через pydantic и переменные окружения.

---

## Логика работы

1. **Пользователь отправляет документ боту в Telegram.**
2. Бот валидирует файл (расширение, размер, имя).
3. Проверяется rate limit пользователя.
4. Бот определяет папку назначения по префиксу имени файла (или предлагает варианты).
5. Документ загружается в нужную папку Google Drive через сервисный аккаунт.
6. Если документ PDF — запускается OCR (PyMuPDF + pytesseract).
7. Извлечённый текст анализируется AI (SimpleRegexAnalyzer или другой).
8. Результаты отправляются пользователю.
9. Все действия логируются (structured logging).
10. Вся статистика и ошибки мониторятся через middleware.

---

## Переменные окружения (.env)

```
BOT_TOKEN=...                # Токен Telegram-бота
ALLOWED_USER_IDS=...         # Список разрешённых user_id (через запятую или JSON)
ADMIN_USER_ID=...            # (опционально) user_id администратора
GOOGLE_SERVICE_ACCOUNT_PATH=payline2-75c36eec2d75.json
GOOGLE_DRIVE_ROOT_FOLDER=18in0UbrSkDNqCGO6AtxCr-NVrf-ktzsX
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///bot.db
MAX_FILE_SIZE_MB=50
DAILY_UPLOAD_LIMIT=100
AI_ANALYSIS_ENABLED=True
GEMINI_API_KEY=...           # (опционально) ключ для AI
OCR_LANGUAGES=rus+eng        # Языки для OCR
OCR_TIMEOUT=30               # Таймаут OCR (сек)
CACHE_TTL=3600               # Время жизни кэша папок (сек)
ENABLE_METRICS=False         # Включить Prometheus-метрики
METRICS_PORT=8000            # Порт для метрик
```

---

## Инструкция по запуску

### 1. Docker (рекомендуется)

1. Установите [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Скопируйте сервисный JSON-файл Google в корень проекта и пропишите его имя в `.env` и `docker-compose.yml`.
3. Запустите:
   ```
   docker compose up --build
   ```

### 2. Локально (без Docker)

1. Установите Python 3.11+ и tesseract-ocr (через brew или apt).
2. Создайте и активируйте виртуальное окружение:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Заполните `.env` (см. выше).
4. Запустите бота (укажите точку входа, например):
   ```
   python main.py
   ```

---

## Тестирование

- Проверьте загрузку PDF, docx, txt, фото, альбомов.
- Проверьте работу лимитов (размер, расширение, rate limit, лимит Gemini).
- Проверьте structured logging (логи в stdout или bot.log).
- Проверьте мониторинг (middleware логирует медленные и ошибочные запросы).
- Проверьте fuzzy-поиск папок и ручной выбор/создание папки.

---

## Безопасность
- Не коммитьте сервисный JSON-файл в git!
- Не публикуйте токены и ключи.
- Все файлы проходят валидацию и rate limiting.

---

## Зависимости для AI-анализа и извлечения текста

- python-docx — для Word (DOCX)
- pytesseract, Pillow — для OCR (JPG, PNG)
- PyMuPDF (fitz) — для PDF
- httpx — для асинхронных запросов к Gemini

Установка:

```
pip install -r requirements.txt
```

Для OCR:

- Установите tesseract-ocr:
  - macOS: `brew install tesseract`
  - Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng`

## Dockerfile (пример)

```dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

WORKDIR /app
COPY --chown=appuser:appuser . .

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

USER appuser
EXPOSE 8000

CMD ["python", "main.py"]
```
