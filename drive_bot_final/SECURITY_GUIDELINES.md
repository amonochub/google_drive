# Security Guidelines для Google Drive Smart Uploader Bot

## 🔒 Основные принципы безопасности

### 1. Управление секретами

#### ❌ НЕ делайте:
```python
# НЕ хардкодите секреты в коде
TELEGRAM_TOKEN = "1234567890:AABBccddEEffGGhhIIjjKKllMMnnOOpp"
GOOGLE_CLIENT_SECRET = "GOCSPX-abcdefghijklmnopqrstuvwxyz"
```

#### ✅ Делайте:
```python
# Используйте переменные окружения
from app.config import settings
bot = Bot(token=settings.bot_token)
```

### 2. Валидация входных данных

#### Проверка файлов:
```python
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.jpg', '.png', '.zip'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

def validate_file(file_data: bytes, filename: str) -> bool:
    # Проверка расширения
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Недопустимое расширение: {ext}")
    
    # Проверка размера
    if len(file_data) > MAX_FILE_SIZE:
        raise ValidationError("Файл слишком большой")
    
    # Проверка MIME-типа
    import magic
    mime_type = magic.from_buffer(file_data, mime=True)
    if not is_allowed_mime_type(mime_type):
        raise ValidationError(f"Недопустимый MIME-тип: {mime_type}")
```

#### Проверка пользовательского ввода:
```python
import re
from html import escape

def validate_filename(filename: str) -> str:
    # Удаление опасных символов
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Экранирование HTML
    filename = escape(filename)
    
    # Ограничение длины
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename
```

### 3. Rate Limiting

```python
from collections import defaultdict
from time import time

class RateLimiter:
    def __init__(self, max_requests: int = 10, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self.requests = defaultdict(list)
    
    def is_allowed(self, user_id: int) -> bool:
        now = time()
        user_requests = self.requests[user_id]
        
        # Удаляем старые запросы
        user_requests[:] = [req_time for req_time in user_requests 
                           if now - req_time < self.window]
        
        # Проверяем лимит
        if len(user_requests) >= self.max_requests:
            return False
        
        user_requests.append(now)
        return True

# Использование
rate_limiter = RateLimiter(max_requests=10, window=60)

@router.message()
async def handle_message(message: Message):
    if not rate_limiter.is_allowed(message.from_user.id):
        await message.reply("Слишком много запросов. Попробуйте позже.")
        return
```

### 4. Логирование безопасности

```python
import structlog

security_log = structlog.get_logger("security")

async def log_security_event(event_type: str, user_id: int, **kwargs):
    security_log.warning(
        "security_event",
        event_type=event_type,
        user_id=user_id,
        timestamp=datetime.utcnow().isoformat(),
        **kwargs
    )

# Примеры использования
await log_security_event("suspicious_file_upload", user_id, filename=filename, size=file_size)
await log_security_event("rate_limit_exceeded", user_id, attempts=attempts)
await log_security_event("unauthorized_access", user_id, action=action)
```

### 5. Обработка ошибок

```python
async def safe_file_processing(file_data: bytes) -> ProcessingResult:
    try:
        # Обработка файла
        result = await process_file(file_data)
        return result
    except ValidationError as e:
        # Логируем ошибку валидации
        log.warning("file_validation_error", error=str(e))
        raise
    except Exception as e:
        # Логируем неожиданную ошибку
        log.error("unexpected_error", error=str(e), exc_info=True)
        raise ProcessingError("Произошла ошибка при обработке файла")
```

### 6. Защита от Path Traversal

```python
import os
from pathlib import Path

def safe_file_path(base_dir: str, filename: str) -> Path:
    # Нормализация пути
    base_path = Path(base_dir).resolve()
    file_path = (base_path / filename).resolve()
    
    # Проверка, что файл находится в разрешенной директории
    if not str(file_path).startswith(str(base_path)):
        raise SecurityError("Path traversal detected")
    
    return file_path
```

### 7. Защита Google Drive API

```python
from google.auth.exceptions import RefreshError
import asyncio

async def safe_drive_request(func, *args, max_retries: int = 3, **kwargs):
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except RefreshError:
            # Проблема с токеном
            await log_security_event("token_refresh_failed", 0)
            raise AuthenticationError("Ошибка авторизации")
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

## 🛡️ Чек-лист безопасности

### Перед деплоем:

- [ ] Все секреты вынесены в переменные окружения
- [ ] Настроен .gitignore для исключения секретов
- [ ] Включена валидация всех входных данных
- [ ] Настроен rate limiting
- [ ] Логируются все события безопасности
- [ ] Используется HTTPS для всех внешних запросов
- [ ] Настроена ротация логов
- [ ] Проведено сканирование на уязвимости

### Регулярные проверки:

- [ ] Обновление зависимостей
- [ ] Проверка логов безопасности
- [ ] Ротация API ключей
- [ ] Мониторинг подозрительной активности

## 🚨 Реагирование на инциденты

### При обнаружении подозрительной активности:

1. **Немедленно:**
   - Заблокировать подозрительного пользователя
   - Сохранить логи
   - Уведомить администратора

2. **В течение часа:**
   - Проанализировать масштаб инцидента
   - Проверить целостность данных
   - При необходимости - ротировать ключи

3. **В течение дня:**
   - Провести полный анализ
   - Обновить системы защиты
   - Задокументировать инцидент

---

**Помните: безопасность - это процесс, а не разовое действие!**