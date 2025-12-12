#!/bin/bash
# manage_docker.sh
# Удобный скрипт для управления Docker-компонентами проекта

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

show_help() {
    cat << EOF
Taxi Bot - Docker Management Script

Использование: ./manage_docker.sh [команда] [компонент]

Команды:
    up [компонент]      - Запустить компонент(ы)
    down [компонент]    - Остановить компонент(ы)
    restart [компонент] - Перезапустить компонент(ы)
    logs [компонент]    - Показать логи компонента
    status              - Показать статус всех компонентов
    rebuild [компонент] - Пересобрать и перезапустить компонент
    clean               - Очистить все (включая volumes)
    help                - Показать эту справку

Компоненты:
    all              - Все компоненты (по умолчанию)
    infra            - Инфраструктура (postgres, redis, rabbitmq)
    app              - Приложения (bot, web, matching_workers, notifications)
    postgres         - PostgreSQL база данных
    redis            - Redis кэш
    rabbitmq         - RabbitMQ брокер сообщений
    bot              - Telegram Bot
    web_admin        - Web Admin панель
    web_client       - Web Client интерфейс (2 экземпляра)
    notifications    - Notifications сервис (HTTP API + NotificationWorker)
    matching_worker  - Matching Workers (2 экземпляра)
    nginx            - Nginx reverse proxy

Примеры:
    ./manage_docker.sh up                    # Запустить всё
    ./manage_docker.sh up infra              # Запустить только инфраструктуру
    ./manage_docker.sh up postgres           # Запустить только PostgreSQL
    ./manage_docker.sh logs bot              # Логи Telegram Bot
    ./manage_docker.sh restart matching_worker # Перезапустить воркеры
    ./manage_docker.sh rebuild nginx         # Пересобрать nginx
    ./manage_docker.sh status                # Статус всех компонентов
EOF
}

# Определяем файлы compose для каждого компонента
get_compose_files() {
    local component=$1
    case $component in
        infra)
            echo "-f docker-compose.infra.yml"
            ;;
        app)
            echo "-f docker-compose.app.yml"
            ;;
        postgres|redis|rabbitmq)
            echo "-f docker-compose.infra.yml"
            ;;
        bot|web_admin|web_client|web_client_1|web_client_2|notifications|matching_worker|matching_worker_1|matching_worker_2|worker|worker_1|worker_2|nginx)
            echo "-f docker-compose.app.yml"
            ;;
        all|*)
            echo "-f docker-compose.yml"
            ;;
    esac
}

# Определяем сервис для компонента
get_service_name() {
    local component=$1
    case $component in
        infra)
            echo ""  # Все сервисы infra
            ;;
        app)
            echo ""  # Все сервисы app
            ;;
        web_client)
            echo "web_client_1 web_client_2"
            ;;
        matching_worker|worker)  # worker для обратной совместимости
            echo "matching_worker_1 matching_worker_2"
            ;;
        all)
            echo ""
            ;;
        *)
            echo "$component"
            ;;
    esac
}

cmd_up() {
    local component=${1:-all}
    local compose_files=$(get_compose_files $component)
    local service=$(get_service_name $component)
    
    print_header "Запуск компонента: $component"
    
    if [ "$component" == "all" ]; then
        print_info "Запуск инфраструктуры..."
        docker-compose -f docker-compose.infra.yml up -d
        print_success "Инфраструктура запущена"
        
        print_info "Ожидание готовности инфраструктуры (10 сек)..."
        sleep 10
        
        print_info "Запуск приложений..."
        docker-compose -f docker-compose.app.yml up -d
        print_success "Приложения запущены"
    elif [ "$component" == "app" ]; then
        print_info "Запуск приложений (требуется запущенная инфраструктура)..."
        docker-compose $compose_files up -d $service
        print_success "Приложения запущены"
    else
        docker-compose $compose_files up -d $service
        print_success "Компонент '$component' запущен"
    fi
}

cmd_down() {
    local component=${1:-all}
    local compose_files=$(get_compose_files $component)
    local service=$(get_service_name $component)
    
    print_header "Остановка компонента: $component"
    
    if [ "$component" == "all" ]; then
        print_info "Остановка приложений..."
        docker-compose -f docker-compose.app.yml down
        
        print_info "Остановка инфраструктуры..."
        docker-compose -f docker-compose.infra.yml down
        print_success "Все компоненты остановлены"
    else
        docker-compose $compose_files stop $service
        print_success "Компонент '$component' остановлен"
    fi
}

cmd_restart() {
    local component=${1:-all}
    print_header "Перезапуск компонента: $component"
    cmd_down $component
    sleep 2
    cmd_up $component
}

cmd_logs() {
    local component=${1:-all}
    local compose_files=$(get_compose_files $component)
    local service=$(get_service_name $component)
    
    print_header "Логи компонента: $component"
    docker-compose $compose_files logs -f --tail=100 $service
}

cmd_status() {
    print_header "Статус компонентов"
    
    echo -e "\n${YELLOW}Инфраструктура:${NC}"
    docker-compose -f docker-compose.infra.yml ps
    
    echo -e "\n${YELLOW}Приложения:${NC}"
    docker-compose -f docker-compose.app.yml ps
}

cmd_rebuild() {
    local component=${1:-all}
    local compose_files=$(get_compose_files $component)
    local service=$(get_service_name $component)
    
    print_header "Пересборка компонента: $component"
    
    docker-compose $compose_files build $service
    print_success "Образ пересобран"
    
    cmd_restart $component
}

cmd_clean() {
    print_header "Очистка всех компонентов и данных"
    print_error "⚠️  ВНИМАНИЕ: Будут удалены ВСЕ данные (БД, Redis, RabbitMQ)!"
    read -p "Продолжить? (yes/no): " confirm
    
    if [ "$confirm" == "yes" ]; then
        docker-compose -f docker-compose.app.yml down -v
        docker-compose -f docker-compose.infra.yml down -v
        docker network rm taxi_network 2>/dev/null || true
        print_success "Все компоненты и данные удалены"
    else
        print_info "Отменено"
    fi
}

# Основная логика
main() {
    local command=${1:-help}
    local component=${2:-all}
    
    case $command in
        up)
            cmd_up $component
            ;;
        down)
            cmd_down $component
            ;;
        restart)
            cmd_restart $component
            ;;
        logs)
            cmd_logs $component
            ;;
        status)
            cmd_status
            ;;
        rebuild)
            cmd_rebuild $component
            ;;
        clean)
            cmd_clean
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Неизвестная команда: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
