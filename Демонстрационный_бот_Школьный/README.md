# Демонстрационный школьный бот

## Быстрый старт

### 1. Клонируйте репозиторий и перейдите в папку
```bash
git clone <your-repo-url>
cd Демонстрационный_бот_Школьный
```

### 2. Создайте файл .env

Пример содержимого:
```
TELEGRAM_TOKEN=ваш_токен_бота
DB_NAME=demo_db
DB_USER=demo_user
DB_PASS=demo_pass
DB_HOST=db
DB_PORT=5432
```

### 3. Соберите и запустите контейнеры
```bash
docker-compose up --build
```

### 4. Проверьте логи
```bash
docker-compose logs -f bot
```

### 5. Остановите контейнеры
```bash
docker-compose down
```

## Структура проекта
- `app/bot.py` — основной код Telegram-бота
- `app/db.py` — модели и подключение к БД
- `app/roles.py` — роли и демо-пользователи
- `app/config.py` — конфиг и переменные окружения
- `Dockerfile`, `docker-compose.yml` — контейнеризация

## Демо-логины
- Учитель: `teacher01` / `teacher`
- Админ: `admin01` / `admin`
- Директор: `director01` / `director`
- Ученик: `student01` / `student`
- Родитель: `parent01` / `parent`
- Психолог: `psy01` / `psy`

## Безопасность
- Не коммитьте .env и другие секреты
- Все сервисы изолированы в internal-сети Docker
- Подробнее — см. SECURITY.md

## Зависимости
- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- aiogram, SQLAlchemy, asyncpg, python-dotenv

## Контакты для Responsible Disclosure
См. SECURITY.md

## Кастомизация и брендирование

- Логотип: замените файл `app/static/logo.png` на свой (размер ~40x40px)
- Favicon: замените `app/static/favicon.png`
- Цвета: измените переменные в `app/static/branding.css`
- Тёмная тема: переключатель в правом верхнем углу
