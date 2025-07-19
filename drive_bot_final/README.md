
# Google Drive Smart Uploader Bot

Telegram-бот для массовой и интеллектуальной загрузки документов в Google Drive с поддержкой:
- "Умного окна" (batch upload с авто-распознаванием имён и wizard)
- Массовой загрузки через ZIP/CSV
- Проверки и валидации документов (OCR, NER, парсер)
- FSM wizard для ручного исправления имён
- Прогресс-бара и подробного UX
- Интеграции с Google Drive API (OAuth2)
- Асинхронной обработки и Celery

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

## Переменные окружения (пример .env)

```
TELEGRAM_TOKEN=your-telegram-token
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
GOOGLE_DRIVE_ROOT=...
REDIS_DSN=redis://localhost:6379/0
```

---

## Массовая загрузка: команды и режимы

- **/bulk preset** — конвейер: один раз вводите метаданные, шлёте пачку файлов.
- **"Умное окно"** — просто кидайте 3–10 файлов подряд, бот сам предложит имена и сводку.
- **ZIP/CSV** — для больших партий: отправьте архив или csv-реестр.

**Пример:**
```
/bulk Демирекс Валиент Договор 20250523
/bulk stop
/bulk status
```

---

## Тесты

```bash
pytest
```

- Примеры тестов: `tests/test_filename_parser.py`, `tests/test_upload.py`, ...
- Для моков используйте `pytest-mock` или встроенные фикстуры.

---

## CI (GitHub Actions)

- Линтинг: black, flake8, mypy
- Тесты: pytest
- Проверка на секреты

Workflow: `.github/workflows/ci.yml`

---

## Безопасность
- Никогда не коммитьте .env, credentials.json и другие секреты!
- Все секреты должны быть в .gitignore и/или GitHub Secrets.

---

## Контакты и поддержка
- [amonochub](https://github.com/amonochub)
- Issues/PR приветствуются!
