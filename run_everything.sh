#!/bin/bash
# run_everything.sh
# Запускает ВСЕ компоненты системы в одном терминале (для разработки)

# Активация venv если нужно
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f "../.venv/bin/activate" ]; then
        source "../.venv/bin/activate"
    elif [ -f ".venv/bin/activate" ]; then
        source ".venv/bin/activate"
    fi
fi

# Функция для остановки всех процессов при выходе
cleanup() {
    echo -e "\n🛑 Остановка всех сервисов..."
    # Получаем список фоновых задач
    JOBS="$(jobs -p)"
    if [ -n "$JOBS" ]; then
        # Отправляем SIGTERM
        kill $JOBS 2>/dev/null
        # Ждем завершения процессов, чтобы они не писали в терминал после выхода скрипта
        wait $JOBS 2>/dev/null
    fi
    docker stop taxi_nginx_dev >/dev/null 2>&1
    echo "✅ Все сервисы остановлены"
}
# Используем только EXIT, чтобы при SIGINT (Ctrl+C) bash сам завершался и вызывал cleanup
trap cleanup EXIT

# Функция для завершения процессов, занимающих порты
kill_existing() {
    echo "🔍 Проверка занятых портов..."
    PORTS="8080 8081 8082 8083 8084 8085 8086 8087 8088 8089 8090 8091"
    for PORT in $PORTS; do
        PID=$(lsof -ti :$PORT)
        if [ ! -z "$PID" ]; then
            echo "⚠️ Порт $PORT занят процессом $PID. Завершаем..."
            kill -9 $PID 2>/dev/null
        fi
    done
    
    # Также ищем процессы по имени entrypoint
    PIDS=$(pgrep -f "python3 entrypoints/")
    if [ ! -z "$PIDS" ]; then
        echo "⚠️ Найдены зависшие процессы entrypoints. Завершаем..."
        echo "$PIDS" | xargs kill -9 2>/dev/null
    fi
}

# Очистка перед запуском
kill_existing

# Очистка логов если RUN_DEV_MODE=true
if grep -q '"RUN_DEV_MODE": true' config/config.json; then
    echo "🧹 Очистка логов (RUN_DEV_MODE=true)..."
    rm -f logs/*.log
fi

# Экспорт переменных окружения для локальной разработки
export USERS_SERVICE_HOST=localhost
export TRIP_SERVICE_HOST=localhost
export PRICING_SERVICE_HOST=localhost
export PAYMENTS_SERVICE_HOST=localhost
export MINIAPP_BFF_HOST=localhost
export REALTIME_WS_GATEWAY_HOST=localhost
export REALTIME_LOCATION_INGEST_HOST=localhost
export ORDER_MATCHING_SERVICE_HOST=localhost

echo "🚀 Запуск Taxi Bot (Full Dev Mode)..."

# 1. Запуск ядра (Микросервисы + Бот + Воркер)
echo "📦 Запуск Core Services (Microservices, Bot, Worker)..."
SERVICE_NAME=core python3 entrypoints/entrypoint_all.py &
CORE_PID=$!

# Ждем немного, чтобы БД и брокеры успели инициализироваться
sleep 5

# 2. Запуск Web Client (Пассажир/Водитель)
echo "📱 Запуск Web Client (:8082)..."
SERVICE_NAME=web_client python3 entrypoints/entrypoint_web_client.py &

# 3. Запуск Web Admin (Админка)
echo "👑 Запуск Web Admin (:8081)..."
SERVICE_NAME=web_admin python3 entrypoints/entrypoint_web_admin.py &

# 4. Запуск Notifications (Уведомления)
echo "🔔 Запуск Notifications Service (:8083)..."
SERVICE_NAME=notifications python3 entrypoints/entrypoint_notifications.py &

# 5. Запуск Nginx (Reverse Proxy) для локальной разработки
echo "🌐 Запуск Nginx (Reverse Proxy)..."
docker stop taxi_nginx_dev >/dev/null 2>&1
docker run --rm -d \
  --name taxi_nginx_dev \
  --network host \
  -v $(pwd)/devops/nginx.local.conf:/etc/nginx/conf.d/default.conf:ro \
  nginx:alpine >/dev/null

echo -e "\n✅ Все компоненты запущены!"
echo "🌐 Web Client: https://app-dev.iebrainlabs.com/ via Nginx или http://localhost:8082"
echo "🌐 Web Admin:  https://app-dev.iebrainlabs.com/admin/ via Nginx или http://localhost:8081"
echo "📝 Логи выводятся в этот терминал. Нажмите Ctrl+C для остановки."

# Ожидание завершения процессов
wait $CORE_PID
