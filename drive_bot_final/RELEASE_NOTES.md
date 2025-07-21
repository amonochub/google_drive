# 🚀 Release: Google Drive Smart Uploader Bot (Production)

## Кратко

**Google Drive Smart Uploader Bot** — production-ready Telegram-бот для интеллектуальной загрузки, валидации и поиска документов в Google Drive.  
В релизе реализованы все best practices: структурированное логирование, тесты, Docker, FSM, интеграция с Google API, продвинутый UX и безопасность.

---

## Основные возможности

- **Массовая загрузка документов** (batch, ZIP, CSV)
- **Автоматический парсер имён файлов** (поддержка разных форматов дат, кириллицы, спецсимволов)
- **FSM wizard** для ручной коррекции метаданных
- **OCR и NER**: извлечение текста и параметров из PDF, DOCX, изображений
- **Интеграция с Google Drive API** (OAuth2, refresh token, публичные ссылки)
- **Асинхронная обработка, Celery, Redis**
- **CBR мониторинг**: отслеживание курсов валют, подписка на уведомления
- **Структурированное логирование** (structlog + orjson)
- **Docker Compose**: healthcheck, переменные окружения, production-ready инфраструктура
- **Полное покрытие тестами** (pytest, edge-cases, FSM, upload, OCR, validate)
- **Безопасность**: все секреты в .env, большие файлы и client_secrets.json исключены из git

---

## Как запустить

```bash
# Клонируйте репозиторий
git clone https://github.com/amonochub/google_drive.git
cd google_drive/drive_bot_final

# Запуск через Docker Compose
docker-compose up --build

# Или вручную:
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # настройте переменные
python -m app.main
```

---

## Переменные окружения

- `TELEGRAM_TOKEN`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`
- `GOOGLE_DRIVE_ROOT_FOLDER`
- `REDIS_DSN`
- `MAX_FILE_SIZE_MB`, `HEAVY_PDF_MB`, `CACHE_TTL`

---

## Тесты

```bash
pytest --disable-warnings -v
```
Покрытие: upload, batch, FSM, OCR, validate, edge-cases.

---

## Важно

- **client_secrets.json** и другие секреты не входят в git — храните их только локально или в CI/CD.
- Все большие файлы и временные проекты удалены из истории репозитория.
- Для production рекомендуется добавить `restart: unless-stopped` в docker-compose.yml.

---

## Контакты

- [amonochub](https://github.com/amonochub)
- Issues/PR приветствуются!

---

**Спасибо за вклад и тестирование! Проект готов к эксплуатации и дальнейшему развитию 🚀** 