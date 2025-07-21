# Performance Optimization Guidelines

## 🚀 Оптимизация производительности Google Drive Smart Uploader Bot

### 1. OCR Оптимизация

#### Проблема: Медленная обработка больших PDF файлов

```python
# ❌ Медленная версия
async def extract_text_slow(pdf_path: str) -> str:
    with fitz.open(pdf_path) as doc:
        text = ""
        for page in doc:
            text += page.get_text()
    return text
```

```python
# ✅ Оптимизированная версия
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

class OptimizedOCR:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cache = {}
    
    async def extract_text_optimized(self, pdf_path: str) -> str:
        # Проверяем кэш
        cache_key = f"{pdf_path}:{os.path.getmtime(pdf_path)}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Обрабатываем по страницам
        pages_text = await self._process_pages_parallel(pdf_path)
        result = "\n".join(pages_text)
        
        # Кэшируем результат
        self.cache[cache_key] = result
        return result
    
    async def _process_pages_parallel(self, pdf_path: str) -> List[str]:
        loop = asyncio.get_event_loop()
        
        # Получаем информацию о страницах
        page_count = await loop.run_in_executor(
            self.executor, self._get_page_count, pdf_path
        )
        
        # Обрабатываем страницы параллельно
        tasks = []
        for page_num in range(page_count):
            task = loop.run_in_executor(
                self.executor, self._extract_page_text, pdf_path, page_num
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    def _extract_page_text(self, pdf_path: str, page_num: int) -> str:
        """Извлечение текста с одной страницы (синхронная)"""
        with fitz.open(pdf_path) as doc:
            page = doc[page_num]
            return page.get_text()
```

### 2. Кэширование с Redis

```python
import redis.asyncio as redis
import orjson
from typing import Optional, Any

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.default_ttl = 3600  # 1 час
    
    async def get(self, key: str) -> Optional[Any]:
        try:
            data = await self.redis.get(key)
            if data:
                return orjson.loads(data)
        except Exception as e:
            log.error("cache_get_error", key=key, error=str(e))
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            ttl = ttl or self.default_ttl
            data = orjson.dumps(value)
            await self.redis.setex(key, ttl, data)
            return True
        except Exception as e:
            log.error("cache_set_error", key=key, error=str(e))
            return False
    
    async def invalidate(self, pattern: str) -> int:
        """Удаление ключей по паттерну"""
        keys = await self.redis.keys(pattern)
        if keys:
            return await self.redis.delete(*keys)
        return 0

# Использование кэша
cache = CacheManager(settings.redis_dsn)

async def get_ocr_result_cached(file_id: str, file_hash: str) -> str:
    cache_key = f"ocr:{file_id}:{file_hash}"
    
    # Проверяем кэш
    cached_result = await cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # Выполняем OCR
    result = await extract_text_optimized(file_path)
    
    # Сохраняем в кэш на 24 часа
    await cache.set(cache_key, result, ttl=86400)
    
    return result
```

### 3. Оптимизация загрузки файлов

```python
import aiofiles
from typing import AsyncGenerator

class StreamingUploader:
    def __init__(self, chunk_size: int = 8192):
        self.chunk_size = chunk_size
    
    async def upload_large_file(self, file_path: str, drive_service) -> str:
        """Потоковая загрузка больших файлов"""
        file_size = os.path.getsize(file_path)
        
        if file_size > 50 * 1024 * 1024:  # > 50MB
            return await self._resumable_upload(file_path, drive_service)
        else:
            return await self._simple_upload(file_path, drive_service)
    
    async def _resumable_upload(self, file_path: str, drive_service) -> str:
        """Resumable upload для больших файлов"""
        media = MediaFileUpload(
            file_path,
            mimetype='application/octet-stream',
            resumable=True,
            chunksize=1024 * 1024  # 1MB chunks
        )
        
        request = drive_service.files().create(
            body={'name': os.path.basename(file_path)},
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info("upload_progress", progress=status.progress() * 100)
        
        return response['id']
    
    async def _simple_upload(self, file_path: str, drive_service) -> str:
        """Простая загрузка для небольших файлов"""
        async with aiofiles.open(file_path, 'rb') as f:
            content = await f.read()
        
        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype='application/octet-stream'
        )
        
        result = drive_service.files().create(
            body={'name': os.path.basename(file_path)},
            media_body=media
        ).execute()
        
        return result['id']
```

### 4. Memory Management

```python
import gc
import psutil
from contextlib import asynccontextmanager

class MemoryManager:
    def __init__(self, max_memory_mb: int = 500):
        self.max_memory_mb = max_memory_mb
    
    def get_memory_usage(self) -> float:
        """Получить текущее использование памяти в MB"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    @asynccontextmanager
    async def memory_limit(self, operation_name: str):
        """Контекстный менеджер для контроля памяти"""
        initial_memory = self.get_memory_usage()
        
        try:
            yield
        finally:
            final_memory = self.get_memory_usage()
            memory_diff = final_memory - initial_memory
            
            log.info(
                "memory_usage",
                operation=operation_name,
                initial_mb=initial_memory,
                final_mb=final_memory,
                diff_mb=memory_diff
            )
            
            # Принудительная очистка если памяти много используется
            if final_memory > self.max_memory_mb:
                gc.collect()
                log.warning("memory_cleanup_forced", memory_mb=final_memory)

# Использование
memory_manager = MemoryManager()

async def process_large_file(file_path: str) -> str:
    async with memory_manager.memory_limit("large_file_processing"):
        # Обработка файла с контролем памяти
        result = await extract_text_optimized(file_path)
        return result
```

### 5. Batch Processing Optimization

```python
from dataclasses import dataclass
from typing import List, Dict, Any
import asyncio

@dataclass
class BatchJob:
    file_id: str
    file_path: str
    priority: int = 1
    metadata: Dict[str, Any] = None

class BatchProcessor:
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue = asyncio.Queue()
        self.workers = []
    
    async def start_workers(self):
        """Запуск воркеров для обработки очереди"""
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
    
    async def stop_workers(self):
        """Остановка воркеров"""
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
    
    async def _worker(self, worker_name: str):
        """Воркер для обработки заданий"""
        while True:
            try:
                job = await self.queue.get()
                
                async with self.semaphore:
                    await self._process_job(job, worker_name)
                
                self.queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("worker_error", worker=worker_name, error=str(e))
    
    async def _process_job(self, job: BatchJob, worker_name: str):
        """Обработка одного задания"""
        start_time = time.time()
        
        try:
            log.info("job_started", job_id=job.file_id, worker=worker_name)
            
            # OCR обработка
            text = await get_ocr_result_cached(job.file_id, job.metadata.get('hash'))
            
            # Загрузка в Drive
            drive_id = await upload_to_drive(job.file_path, text)
            
            processing_time = time.time() - start_time
            log.info(
                "job_completed",
                job_id=job.file_id,
                worker=worker_name,
                processing_time=processing_time,
                drive_id=drive_id
            )
            
        except Exception as e:
            log.error("job_failed", job_id=job.file_id, worker=worker_name, error=str(e))
            raise
    
    async def add_job(self, job: BatchJob):
        """Добавить задание в очередь"""
        await self.queue.put(job)
    
    async def wait_completion(self):
        """Ждать завершения всех заданий"""
        await self.queue.join()

# Использование
batch_processor = BatchProcessor(max_concurrent=3)

async def process_files_batch(files: List[str]):
    await batch_processor.start_workers()
    
    try:
        # Добавляем задания
        for i, file_path in enumerate(files):
            job = BatchJob(
                file_id=f"file_{i}",
                file_path=file_path,
                priority=1,
                metadata={'hash': calculate_file_hash(file_path)}
            )
            await batch_processor.add_job(job)
        
        # Ждем завершения
        await batch_processor.wait_completion()
        
    finally:
        await batch_processor.stop_workers()
```

### 6. Database Connection Pooling

```python
import asyncpg
from contextlib import asynccontextmanager

class DatabasePool:
    def __init__(self, dsn: str, min_size: int = 5, max_size: int = 20):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool = None
    
    async def init_pool(self):
        """Инициализация пула соединений"""
        self.pool = await asyncpg.create_pool(
            self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=60
        )
    
    async def close_pool(self):
        """Закрытие пула соединений"""
        if self.pool:
            await self.pool.close()
    
    @asynccontextmanager
    async def acquire(self):
        """Получить соединение из пула"""
        async with self.pool.acquire() as connection:
            yield connection
```

## 📊 Мониторинг производительности

```python
import time
from functools import wraps

def monitor_performance(operation_name: str):
    """Декоратор для мониторинга производительности"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = memory_manager.get_memory_usage()
            
            try:
                result = await func(*args, **kwargs)
                
                execution_time = time.time() - start_time
                end_memory = memory_manager.get_memory_usage()
                memory_diff = end_memory - start_memory
                
                log.info(
                    "performance_metrics",
                    operation=operation_name,
                    execution_time=execution_time,
                    memory_usage_mb=end_memory,
                    memory_diff_mb=memory_diff
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                log.error(
                    "performance_error",
                    operation=operation_name,
                    execution_time=execution_time,
                    error=str(e)
                )
                raise
        
        return wrapper
    return decorator

# Использование
@monitor_performance("ocr_processing")
async def extract_text_monitored(file_path: str) -> str:
    return await extract_text_optimized(file_path)
```

## 🎯 Performance Checklist

### Перед деплоем:
- [ ] Настроен Redis кэш для OCR результатов
- [ ] Реализован connection pooling
- [ ] Добавлен мониторинг памяти
- [ ] Оптимизирована загрузка больших файлов
- [ ] Настроен batch processing

### Регулярный мониторинг:
- [ ] Время отклика API
- [ ] Использование памяти
- [ ] Размер кэша Redis
- [ ] Количество активных соединений
- [ ] Пропускная способность

---

**Цель: обработка файлов < 5 сек для файлов < 10MB, < 30 сек для файлов < 50MB**