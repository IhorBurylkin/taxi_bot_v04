#!/bin/bash
# run_tests.sh
# Скрипт для запуска unit тестов проекта

set -e

echo "==================================="
echo "Запуск unit тестов Taxi Bot"
echo "==================================="

# Проверка наличия pytest
if ! python3 -c "import pytest" 2>/dev/null; then
    echo "❌ pytest не установлен"
    echo "Установка pytest и зависимостей..."
    pip3 install pytest pytest-asyncio pytest-cov --user || {
        echo "❌ Не удалось установить pytest"
        echo "Попробуйте установить вручную:"
        echo "  pip3 install pytest pytest-asyncio pytest-cov"
        exit 1
    }
fi

# Запуск тестов
echo ""
echo "Запуск всех тестов..."
python3 -m pytest tests/ -v --tb=short --color=yes

# Проверка результата
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Все тесты пройдены успешно!"
else
    echo ""
    echo "❌ Некоторые тесты провалились"
    exit 1
fi

# Опционально: запуск с покрытием
# python3 -m pytest tests/ --cov=src --cov-report=html --cov-report=term
