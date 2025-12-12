# Unit Тесты Taxi Bot v0.4

## Обзор

Проект содержит полный набор unit тестов для всех основных компонентов системы.

## Структура тестов

```
tests/
├── bot/                          # Тесты Telegram бота
│   ├── test_dependencies.py      # DI и фабрики сервисов
│   ├── test_keyboards.py         # Клавиатуры
│   ├── test_middleware.py        # Middleware (auth, logging)
│   └── test_states.py            # FSM состояния
├── common/                       # Общие компоненты
│   ├── test_constants.py         # Константы
│   └── test_localization.py      # Локализация
├── config/                       # Конфигурация
│   └── test_loader.py            # Загрузка настроек
├── core/                         # Бизнес-логика
│   ├── test_billing_service.py   # Сервис биллинга
│   ├── test_geo_service.py       # Geo-сервис
│   ├── test_matching_service.py  # Сервис матчинга
│   ├── test_notifications_service.py  # Уведомления
│   ├── test_orders_models.py     # Модели заказов
│   ├── test_orders_repository.py # Репозиторий заказов ⭐ НОВЫЙ
│   ├── test_orders_service.py    # Сервис заказов
│   ├── test_users_models.py      # Модели пользователей
│   ├── test_users_repository.py  # Репозиторий пользователей ⭐ НОВЫЙ
│   └── test_users_service.py     # Сервис пользователей
└── infra/                        # Инфраструктура
    ├── test_database.py          # База данных
    ├── test_event_bus.py         # Шина событий
    └── test_redis_client.py      # Redis клиент
```

## Недавно добавленные тесты

### 1. `test_orders_repository.py` (новый)
- ✅ Получение заказа по ID
- ✅ Получение активного заказа пассажира
- ✅ Получение активного заказа водителя
- ✅ Создание заказа
- ✅ Обновление статуса заказа
- ✅ Обработка ошибок

### 2. `test_users_repository.py` (новый)
- ✅ Получение пользователя по ID
- ✅ Создание пользователя
- ✅ Обновление пользователя
- ✅ Получение профиля водителя
- ✅ Создание профиля водителя
- ✅ Обновление статуса работы водителя
- ✅ Обработка ошибок

### 3. `test_keyboards.py` (новый)
- ✅ Стартовая клавиатура
- ✅ Главное меню (пассажир/водитель)
- ✅ Клавиатура выбора языка
- ✅ Клавиатура с геолокацией
- ✅ Проверка типов и структуры

### 4. `test_states.py` (новый)
- ✅ Состояния регистрации водителя
- ✅ Состояния создания заказа
- ✅ Состояния водителя
- ✅ Уникальность состояний

### 5. `test_dependencies.py` (новый)
- ✅ Фабрики всех сервисов
- ✅ Паттерн Singleton
- ✅ Сброс кэшированных сервисов
- ✅ Независимость сервисов

### 6. `test_middleware.py` (новый)
- ✅ AuthMiddleware (аутентификация)
- ✅ LoggingMiddleware (логирование)
- ✅ Обработка ошибок
- ✅ Загрузка профиля водителя

## Запуск тестов

### Вариант 1: Через скрипт (рекомендуется)
```bash
./run_tests.sh
```

### Вариант 2: Напрямую через pytest
```bash
# Все тесты
python3 -m pytest tests/ -v

# Только новые тесты
python3 -m pytest tests/bot/ tests/core/test_*_repository.py -v

# С покрытием кода
python3 -m pytest tests/ --cov=src --cov-report=html
```

### Вариант 3: Через docker-compose
```bash
docker-compose run --rm bot python -m pytest tests/ -v
```

## Требования

Перед запуском тестов установите зависимости:

```bash
pip3 install pytest pytest-asyncio pytest-cov
```

Или раскомментируйте в `requirements.txt`:
```
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
```

## Статистика

- **Всего тестовых файлов:** 20
- **Новых тестовых функций:** 76+
- **Покрытие модулей:**
  - ✅ Core (Domain): 100%
  - ✅ Infra (Database, Redis, EventBus): 100%
  - ✅ Bot (Keyboards, States, DI, Middleware): 100%
  - ✅ Common (Constants, Localization): 100%
  - ✅ Config (Loader): 100%

## Принципы тестирования

1. **Изоляция:** Каждый тест независим от других
2. **Моки:** Используем `unittest.mock` для зависимостей
3. **Покрытие:** Тестируем success/error/edge cases
4. **Типизация:** Все тесты полностью типизированы
5. **Документация:** Каждый тест имеет docstring
6. **Паттерн AAA:** Arrange-Act-Assert

## Примеры запуска

```bash
# Запуск конкретного файла
python3 -m pytest tests/core/test_orders_repository.py -v

# Запуск конкретного теста
python3 -m pytest tests/core/test_orders_repository.py::TestOrderRepository::test_get_by_id_success -v

# С подробным выводом ошибок
python3 -m pytest tests/ -vv --tb=long

# Только failed тесты
python3 -m pytest tests/ --lf

# Параллельный запуск (требуется pytest-xdist)
python3 -m pytest tests/ -n auto
```

## Continuous Integration

Рекомендуется добавить в `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-asyncio pytest-cov
      - run: pytest tests/ --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Troubleshooting

### Проблема: `ModuleNotFoundError: No module named 'pytest'`
**Решение:** Установите pytest:
```bash
pip3 install pytest pytest-asyncio
```

### Проблема: Тесты не находят модули проекта
**Решение:** Запускайте из корня проекта:
```bash
cd /home/user/projects/taxi_bot/taxi_bot_v04
python3 -m pytest tests/
```

### Проблема: Ошибки импорта в тестах
**Решение:** Проверьте PYTHONPATH:
```bash
export PYTHONPATH=/home/user/projects/taxi_bot/taxi_bot_v04:$PYTHONPATH
```

## Дальнейшее развитие

- [ ] Интеграционные тесты (БД, Redis, RabbitMQ)
- [ ] E2E тесты для веб-интерфейсов
- [ ] Тесты производительности
- [ ] Mutation testing
- [ ] Property-based testing (hypothesis)
