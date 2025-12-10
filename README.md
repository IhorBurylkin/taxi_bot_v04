# Taxi Bot v2.0

Современный Telegram-бот для службы такси с веб-интерфейсом.

## Архитектура

Проект построен по принципу **Modular Monolith** с готовностью к переходу на микросервисы.

```
src/
├── common/          # Общие утилиты, константы, логгер
├── config/          # Загрузчик конфигурации (Pydantic)
├── db/              # Инициализация БД и миграции
├── core/            # Чистая бизнес-логика (Domain Layer)
│   ├── users/       # Домен пользователей
│   ├── orders/      # Домен заказов
│   ├── matching/    # Домен поиска водителей
│   ├── geo/         # Google Maps API
│   ├── billing/     # Биллинг и оплата
│   └── notifications/  # Уведомления
├── infra/           # Инфраструктурный слой (DB, Redis, RMQ)
├── bot/             # Telegram Bot (aiogram 3.x)
├── web/             # Web UI (NiceGUI/FastAPI)
└── worker/          # Фоновые задачи
```

## Технологии

- **Python 3.12+**
- **aiogram 3.x** - Telegram Bot API
- **NiceGUI** - Web UI (на базе FastAPI)
- **asyncpg** - PostgreSQL
- **redis** - Кэширование и Geo-индекс
- **aio_pika** - RabbitMQ
- **Pydantic** - Валидация данных

## Быстрый старт

### 1. Клонирование и настройка

```bash
cd taxi_bot_v04
cp .env.example .env
# Заполните .env своими значениями
```

### 2. Запуск через Docker Compose

```bash
docker-compose up -d
```

### 3. Запуск для разработки

```bash
# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python main.py
```

## Конфигурация

Все настройки хранятся в `config/config.json`. Секретные данные (токены, пароли) должны передаваться через переменные окружения.

## Разработка

### Структура конфига

| Блок | Описание |
|------|----------|
| `_comment_system` | Системные настройки |
| `_comment_logging` | Логирование |
| `_comment_telegram` | Telegram API |
| `_comment_database` | PostgreSQL |
| `_comment_redis` | Redis |
| `_comment_rabbitmq` | RabbitMQ |
| `_comment_fares` | Тарифы |

### Добавление новой константы

1. Добавить в `config/config.json`
2. Добавить поле в Pydantic модель (`src/config/loader.py`)
3. Использовать через `from src.config import settings`

## Логирование

Система логирования поддерживает автоматическую трассировку вызовов:

```python
from src.common.logger import log_info
from src.common.constants import TypeMsg

await log_info("Сообщение", type_msg=TypeMsg.INFO)
# Вывод:
# [2025-12-10 21:43:39] INFO - Сообщение
#     ↳ Called from: module.function() [file.py:156]
```

**Документация:**
- `docs/logger_caller_quickstart.md` — быстрый старт
- `docs/logger_caller_checker.md` — подробное описание

## Тестирование

```bash
# Тест логирования
python test_logger_caller.py

# Запуск бота
python main.py --bot

# Запуск веб-интерфейса
python main.py --web
```

## Лицензия

MIT
