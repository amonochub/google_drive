
# Google Drive Smart Uploader Bot

Telegram-бот для массовой и интеллектуальной загрузки документов в Google Drive с поддержкой:
- "Умного окна" (batch upload с авто-распознаванием имён и wizard)
- Массовой загрузки через ZIP/CSV
- Проверки и валидации документов (OCR, NER, парсер)
- FSM wizard для ручного исправления имён
- Прогресс-бара и подробного UX
- Интеграции с Google Drive API (OAuth2)
- Асинхронной обработки и Celery
- Структурированного логирования (structlog)
- Docker-окружения и healthcheck

---

## Быстрый старт

```bash
# Клонируйте репозиторий
 git clone https://github.com/amonochub/google_drive.git
 cd google_drive/drive_bot_final

# Установите зависимости
 python3.11 -m venv venv
 source venv/bin/activate
 pip install -r requirements.txt

# Скопируйте и настройте .env (НЕ коммитьте!)
 cp .env.example .env
# Заполните переменные: TELEGRAM_TOKEN, GOOGLE_CLIENT_ID, ...

# Запустите бота
 python -m app.main
```

---

## Запуск через Docker Compose

```bash
# Соберите и запустите сервисы (бот + Redis)
docker-compose up --build
```

- Бот стартует только после того, как Redis станет healthy
- Все переменные окружения можно задать через .env или docker-compose.yml

---

## Переменные окружения (пример .env)

```
TELEGRAM_TOKEN=your-telegram-token
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
GOOGLE_DRIVE_ROOT_FOLDER=...
REDIS_DSN=redis://redis:6379/0
MAX_FILE_SIZE_MB=50
HEAVY_PDF_MB=20
CACHE_TTL=45
```

---

## Структура проекта

```
drive_bot_final/
├── app/
│   ├── handlers/         # Хендлеры aiogram FSM, меню, upload, validate
│   ├── services/         # Интеграции: Google Drive, OCR, Celery, CBR
│   ├── utils/            # Парсеры, валидация, вспомогательные функции
│   ├── config.py         # Pydantic-настройки
│   ├── main.py           # Точка входа
│   └── ...
├── tests/                # Pytest-тесты (upload, ocr, validate, FSM, batch)
├── requirements.txt
├── docker-compose.yml
├── README.md
└── ...
```

---

## Массовая загрузка: команды и режимы

- **/bulk preset** — конвейер: один раз вводите метаданные, шлёте пачку файлов.
- **"Умное окно"** — просто кидайте 3–10 файлов подряд, бот сам предложит имена и сводку.
- **ZIP/CSV** — для больших партий: отправьте архив или csv-реестр.

**Пример:**
```
/массовая Демирекс Валиент Договор 20250523
/массовая стоп
/массовая статус
```

---

## Тесты

```bash
pytest --disable-warnings -v
```

- Примеры тестов: `tests/test_filename_parser.py`, `tests/test_upload.py`, ...
- Для моков используйте `pytest-mock` или встроенные фикстуры.
- Покрытие: upload, batch, FSM, OCR, validate, edge-cases

---

## CI (GitHub Actions)

- Линтинг: black, flake8, mypy
- Тесты: pytest
- Проверка на секреты

Workflow: `.github/workflows/ci.yml`

---

## Архитектура и best practices
- Асинхронный aiogram 3.x, FSM, reply/inline клавиатуры
- Структурированное логирование через structlog (JSON)
- Валидация файлов: расширение, размер, опасные символы
- Exponential backoff для Google Drive API
- Все секреты — только в .env, .gitignore
- Docker healthcheck для Redis и бота
- Покрытие тестами всех критичных сценариев

---

## Безопасность
- Никогда не коммитьте .env, credentials.json и другие секреты!
- Все секреты должны быть в .gitignore и/или GitHub Secrets.

---

## Контакты и поддержка
- [amonochub](https://github.com/amonochub)
- Issues/PR приветствуются!
