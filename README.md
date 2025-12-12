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

### 2. Запуск через Docker Compose (рекомендуется)

```bash
# Запустить всё (инфраструктура + приложения)
./manage_docker.sh up

# ИЛИ поэтапно:
./manage_docker.sh up infra   # PostgreSQL, Redis, RabbitMQ
./manage_docker.sh up app      # Bot, Web, Workers, Notifications

# Проверить статус
./manage_docker.sh status

# Логи
./manage_docker.sh logs bot
```

**Подробнее:** [Docker Quick Start](docs/docker_quickstart.md)

### 3. Запуск для разработки

#### Вариант 1: Фоновый режим (рекомендуется)

```bash
# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск инфраструктуры в Docker
./manage_docker.sh up infra

# Запуск всех компонентов в фоне
./run_dev.sh start        # Запуск
./run_dev.sh status       # Проверка статуса
./run_dev.sh logs         # Просмотр логов
./run_dev.sh restart      # Перезапуск
./run_dev.sh stop         # Остановка
```

**Подробнее:** [Использование run_dev.sh](docs/run_dev_usage.md)

#### Вариант 2: Интерактивный режим

```bash
# Запуск приложения в текущем терминале (Ctrl+C для остановки)
python entrypoint_all.py  # Все компоненты
python main.py            # Интерактивный выбор
python main.py bot        # Только Telegram Bot
python main.py web_admin  # Только Admin UI
python main.py web_client # Только Client UI
python main.py notifications  # Только Notifications
python main.py matching_worker # Только MatchingWorker

# Инфраструктура (только через Docker)
python main.py postgres   # Подсказка для запуска PostgreSQL
python main.py redis      # Подсказка для запуска Redis
python main.py rabbitmq   # Подсказка для запуска RabbitMQ
```

## Модульная Docker-архитектура

Проект использует модульную архитектуру с разделением на:

### Инфраструктура (docker-compose.infra.yml)
- **PostgreSQL 16** — база данных
- **Redis 7** — кэш и Geo-индекс
- **RabbitMQ 3.12** — брокер сообщений

### Приложения (docker-compose.app.yml)
- **Nginx** — reverse proxy (порт 8080)
- **Telegram Bot** — основной бот (интерактивное взаимодействие)
- **Web Admin** — панель администратора (порт 8081)
- **Web Client** — клиентский интерфейс, 2 экземпляра (8082, 8092)
- **Notifications** — HTTP API + NotificationWorker (порт 8083, отправка уведомлений)
- **MatchingWorkers** — подбор водителей, 2 экземпляра

**Преимущества:**
- ✅ Независимое масштабирование компонентов
- ✅ Изолированные обновления и развертывание
- ✅ Возможность использования managed-сервисов (AWS RDS, Redis Cloud)
- ✅ Упрощенное тестирование и отладка

**Подробнее:** [Модульная Docker-архитектура](docs/docker_modular_architecture.md)

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
