#!/bin/bash
# run_dev.sh
# Скрипт для удобного запуска и остановки приложения в режиме разработки

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# PID файл
PID_FILE="$PROJECT_DIR/.dev_run.pid"

# Функция для вывода сообщений
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Функция для проверки, запущено ли приложение
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Функция для остановки приложения
stop_app() {
    log_info "Остановка приложения..."
    
    if is_running; then
        local pid=$(cat "$PID_FILE")
        log_info "Отправка SIGTERM процессу $pid..."
        kill -TERM "$pid" 2>/dev/null || true
        
        # Ждём до 10 секунд
        local count=0
        while [ $count -lt 10 ] && ps -p "$pid" > /dev/null 2>&1; do
            sleep 1
            count=$((count + 1))
            echo -n "."
        done
        echo ""
        
        # Если всё ещё работает, используем SIGKILL
        if ps -p "$pid" > /dev/null 2>&1; then
            log_warn "Процесс не остановился, отправка SIGKILL..."
            kill -KILL "$pid" 2>/dev/null || true
            sleep 1
        fi
        
        # Очищаем PID файл
        rm -f "$PID_FILE"
        
        # Очищаем оставшиеся процессы Python
        pkill -f "entrypoint_all.py" 2>/dev/null || true
        pkill -f "main.py.*mode=all" 2>/dev/null || true
        
        log_info "✅ Приложение остановлено"
    else
        log_warn "Приложение не запущено"
        # На всякий случай очищаем процессы
        pkill -f "entrypoint_all.py" 2>/dev/null || true
        pkill -f "main.py.*mode=all" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
}

# Функция для запуска приложения
start_app() {
    log_info "Запуск приложения в режиме разработки..."
    
    if is_running; then
        log_error "Приложение уже запущено (PID: $(cat $PID_FILE))"
        log_info "Используйте '$0 stop' для остановки или '$0 restart' для перезапуска"
        exit 1
    fi
    
    # Проверяем виртуальное окружение
    if [ -z "$VIRTUAL_ENV" ]; then
        log_warn "Виртуальное окружение не активировано"
        if [ -f "$PROJECT_DIR/../.venv/bin/activate" ]; then
            log_info "Активация виртуального окружения..."
            source "$PROJECT_DIR/../.venv/bin/activate"
        else
            log_error "Виртуальное окружение не найдено"
            exit 1
        fi
    fi
    
    # Запускаем приложение в фоне
    log_info "Запуск entrypoint_all.py..."
    nohup python "$PROJECT_DIR/entrypoint_all.py" > "$PROJECT_DIR/logs/dev_run.log" 2>&1 &
    local pid=$!
    
    # Сохраняем PID
    echo "$pid" > "$PID_FILE"
    
    # Даём время на запуск
    sleep 2
    
    if ps -p "$pid" > /dev/null 2>&1; then
        log_info "✅ Приложение запущено (PID: $pid)"
        log_info "Логи: tail -f $PROJECT_DIR/logs/dev_run.log"
        log_info "Остановка: $0 stop"
    else
        log_error "❌ Не удалось запустить приложение"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Функция для перезапуска
restart_app() {
    log_info "Перезапуск приложения..."
    stop_app
    sleep 2
    start_app
}

# Функция для проверки статуса
status_app() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        log_info "✅ Приложение запущено (PID: $pid)"
        ps -p "$pid" -o pid,etime,cmd
    else
        log_warn "❌ Приложение не запущено"
    fi
}

# Функция для просмотра логов
logs_app() {
    if [ -f "$PROJECT_DIR/logs/dev_run.log" ]; then
        tail -f "$PROJECT_DIR/logs/dev_run.log"
    else
        log_error "Файл логов не найден"
        exit 1
    fi
}

# Основная логика
case "${1:-}" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        status_app
        ;;
    logs)
        logs_app
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "  start   - Запустить приложение в фоне"
        echo "  stop    - Остановить приложение"
        echo "  restart - Перезапустить приложение"
        echo "  status  - Показать статус приложения"
        echo "  logs    - Просмотр логов (tail -f)"
        exit 1
        ;;
esac
