
# Refactored Drive Bot

Минималистичный Telegram-бот на **aiogram 3**, который:

* Сохраняет документы в Google Drive (логика загрузки не изменена).
* Делает OCR для PDF/JPEG/PNG через *tesseract*.
* Извлекает ключевые реквизиты регулярками.
* Команда **/check** (в ответ на файл) показывает найденные параметры.

## Запуск

```bash
cp .env.example .env  # заполните токен и id папки
docker compose up --build
```

## Получаем refresh-token для Google Drive

Один раз на локальной машине:

```bash
python -m pip install --upgrade google-auth-oauthlib google-auth-httplib2
python scripts/get_refresh_token.py  # скрипт выведет токен
```

### CI

Каждый push запускает GitHub Actions: lint + unit-tests.  
Workflow лежит в `.github/workflows/ci.yml`.
