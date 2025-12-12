#!/usr/bin/env python3
# main.py
"""
Главная точка входа приложения Taxi Bot.
Запускает Telegram Bot, Web UI или Workers в зависимости от аргументов.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Optional

from src.config import settings
from src.common.logger import setup_logging, log_info, log_error
from src.common.constants import TypeMsg
from src.infra.database import init_db, close_db
from src.infra.redis_client import init_redis, close_redis
from src.infra.event_bus import init_event_bus, close_event_bus


# Глобальный флаг для graceful shutdown
_shutdown_event: asyncio.Event | None = None
_running_tasks: list[asyncio.Task] = []


def setup_signal_handlers() -> None:
    """Настраивает обработчики сигналов для graceful shutdown."""
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    def signal_handler(sig: int) -> None:
        """Обработчик сигналов SIGINT и SIGTERM."""
        if _shutdown_event and not _shutdown_event.is_set():
            print(f"\nПолучен сигнал остановки (sig={sig}), завершаем работу...")
            _shutdown_event.set()
            # Отменяем все запущенные задачи
            for task in _running_tasks:
                if not task.done():
                    task.cancel()
    
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    except NotImplementedError:
        # Windows не поддерживает add_signal_handler
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s))
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s))


async def init_infrastructure() -> None:
    """Инициализирует все подключения к инфраструктуре."""
    await log_info("Инициализация инфраструктуры...", type_msg=TypeMsg.INFO)
    
    # Подключение к БД
    await init_db()
    await log_info("PostgreSQL подключён", type_msg=TypeMsg.DEBUG)
    
    # Подключение к Redis
    await init_redis()
    await log_info("Redis подключён", type_msg=TypeMsg.DEBUG)
    
    # Подключение к RabbitMQ
    await init_event_bus()
    await log_info("RabbitMQ подключён", type_msg=TypeMsg.DEBUG)
    
    await log_info("Инфраструктура инициализирована", type_msg=TypeMsg.INFO)


async def close_infrastructure() -> None:
    """Закрывает все подключения."""
    await log_info("Закрытие подключений...", type_msg=TypeMsg.INFO)
    
    await close_event_bus()
    await close_redis()
    await close_db()
    
    await log_info("Подключения закрыты", type_msg=TypeMsg.INFO)


async def warmup_cache() -> None:
    """Прогрев кэша при старте."""
    await log_info("Прогрев кэша...", type_msg=TypeMsg.DEBUG)
    # Здесь можно загрузить часто используемые данные в Redis
    await log_info("Кэш прогрет", type_msg=TypeMsg.DEBUG)


async def run_tests() -> bool:
    """
    Запускает все unit тесты.
    
    Returns:
        True если все тесты прошли, False иначе
    """
    await log_info("Запуск unit тестов...", type_msg=TypeMsg.INFO)
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            cwd=str(get_project_root()),
            capture_output=True,
            text=True,
            timeout=300,  # 5 минут
        )
        
        if result.returncode == 0:
            await log_info("✅ Все тесты прошли успешно", type_msg=TypeMsg.INFO)
            return True
        else:
            await log_error(f"❌ Тесты завершились с ошибками:\n{result.stdout}\n{result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        await log_error("❌ Превышено время ожидания выполнения тестов (5 мин)")
        return False
    except Exception as e:
        await log_error(f"❌ Ошибка при запуске тестов: {e}")
        return False


def get_project_root():
    """Возвращает корневую директорию проекта."""
    from pathlib import Path
    return Path(__file__).parent


async def run_bot() -> None:
    """Запускает Telegram Bot с попыткой использовать webhook, затем polling."""
    from src.bot.app import create_bot, create_dispatcher, setup_webhook, remove_webhook
    from aiohttp import web
    
    await log_info("Запуск Telegram Bot...", type_msg=TypeMsg.INFO)
    
    bot = create_bot()
    dp = create_dispatcher()
    
    try:
        # Попытка использовать webhook если включено в настройках
        use_webhook = settings.telegram.USE_WEBHOOK
        webhook_url = settings.telegram.WEBHOOK_URL_MAIN
        
        await log_info(f"USE_WEBHOOK = {use_webhook}, WEBHOOK_URL_MAIN = {webhook_url}", type_msg=TypeMsg.DEBUG)
        
        if use_webhook and webhook_url:
            try:
                await log_info("Попытка настройки webhook...", type_msg=TypeMsg.INFO)
                await setup_webhook(
                    bot=bot,
                    webhook_url=settings.telegram.WEBHOOK_URL_MAIN,
                    secret=settings.telegram.WEBHOOK_SECRET or "",
                )
                
                # Настраиваем aiohttp для приема webhook
                app = web.Application()
                webhook_path = settings.telegram.WEBHOOK_PATH
                
                async def handle_webhook(request):
                    """Обрабатывает входящие webhook запросы."""
                    update_dict = await request.json()
                    from aiogram.types import Update
                    update = Update(**update_dict)
                    await dp.feed_update(bot, update)
                    return web.Response()
                
                app.router.add_post(f"{webhook_path}/{settings.telegram.BOT_TOKEN}", handle_webhook)
                
                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(
                    runner,
                    host=settings.telegram.WEBAPP_HOST,
                    port=settings.telegram.WEBAPP_PORT,
                )
                await site.start()
                
                await log_info(
                    f"Webhook успешно настроен на {settings.telegram.WEBHOOK_URL_MAIN}",
                    type_msg=TypeMsg.INFO,
                )
                await log_info(
                    f"Bot запущен в режиме webhook на {settings.telegram.WEBAPP_HOST}:{settings.telegram.WEBAPP_PORT}",
                    type_msg=TypeMsg.INFO,
                )
                
                # Держим приложение запущенным до получения сигнала остановки
                try:
                    global _shutdown_event
                    if _shutdown_event:
                        await _shutdown_event.wait()
                    else:
                        await asyncio.Event().wait()
                except (KeyboardInterrupt, asyncio.CancelledError):
                    await log_info("Bot (webhook): получен сигнал остановки", type_msg=TypeMsg.DEBUG)
                finally:
                    await log_info("Bot (webhook): остановка сервера...", type_msg=TypeMsg.DEBUG)
                    await runner.cleanup()
                    
            except Exception as e:
                await log_error(f"Не удалось настроить webhook: {e}")
                await log_info("Переключение на режим polling...", type_msg=TypeMsg.INFO)
                
                # Удаляем webhook если не удалось настроить
                try:
                    await remove_webhook(bot)
                except Exception:
                    pass
                
                # Запускаем polling
                await log_info("Bot запущен в режиме polling", type_msg=TypeMsg.INFO)
                try:
                    await dp.start_polling(bot)
                except asyncio.CancelledError:
                    await log_info("Bot (polling): получен сигнал остановки", type_msg=TypeMsg.DEBUG)
                    raise
        else:
            # Запуск в режиме polling
            await log_info(
                f"Webhook отключен (USE_WEBHOOK={use_webhook}, WEBHOOK_URL={webhook_url}). "
                f"Запуск в режиме polling",
                type_msg=TypeMsg.INFO
            )
            try:
                await dp.start_polling(bot)
            except asyncio.CancelledError:
                await log_info("Bot (polling): получен сигнал остановки", type_msg=TypeMsg.DEBUG)
                raise
            
    except asyncio.CancelledError:
        await log_info("Bot: завершение работы...", type_msg=TypeMsg.INFO)
        raise
    finally:
        await log_info("Bot: закрытие сессии...", type_msg=TypeMsg.DEBUG)
        await bot.session.close()
        await log_info("Bot остановлен", type_msg=TypeMsg.INFO)


async def run_web() -> None:
    """Запускает Web Admin (для обратной совместимости)."""
    await log_info("УСТАРЕВШИЙ РЕЖИМ: используйте 'web_admin' вместо 'web'", type_msg=TypeMsg.WARNING)
    await run_web_admin()


async def run_web_admin() -> None:
    """Запускает Web Admin UI."""
    from src.web_admin.app import run_web as start_web_admin
    
    await log_info("Запуск Web Admin UI...", type_msg=TypeMsg.INFO)
    start_web_admin(
        host=settings.telegram.WEBAPP_HOST,
        port=settings.deployment.WEB_ADMIN_PORT,
    )


async def run_web_client() -> None:
    """Запускает Web Client UI."""
    from src.web_client.app import run_web_client as start_web_client
    
    await log_info("Запуск Web Client UI...", type_msg=TypeMsg.INFO)
    start_web_client(
        host=settings.telegram.WEBAPP_HOST,
        port=settings.deployment.WEB_CLIENT_PORT,
    )


async def run_notifications() -> None:
    """Запускает сервис уведомлений."""
    from src.notifications.app import run_notifications as start_notifications
    
    await log_info("Запуск Notifications сервиса...", type_msg=TypeMsg.INFO)
    start_notifications(
        host=settings.telegram.WEBAPP_HOST,
        port=settings.deployment.NOTIFICATIONS_PORT,
    )


async def run_matching_worker() -> None:
    """Запускает MatchingWorker для подбора водителей."""
    from src.worker.runner import run_workers as start_matching_workers
    
    await log_info("Запуск MatchingWorker...", type_msg=TypeMsg.INFO)
    
    # При запуске через main.py инфраструктура уже инициализирована
    # (в RUN_DEV_MODE=true или через init_infrastructure())
    await start_matching_workers(init_infra=False)


# === Микросервисы Phase 1: Core Services ===

async def run_users_service() -> None:
    """Запускает Users Service (управление профилями, водителями)."""
    import uvicorn
    
    await log_info(
        f"Запуск Users Service на порту {settings.deployment.USERS_SERVICE_PORT}...",
        type_msg=TypeMsg.INFO
    )
    
    config = uvicorn.Config(
        "src.services.users.app:app",
        host="0.0.0.0",
        port=settings.deployment.USERS_SERVICE_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        await log_info("Users Service: graceful shutdown", type_msg=TypeMsg.DEBUG)
        await server.shutdown()


async def run_trip_service() -> None:
    """Запускает Trip Service (state machine поездок)."""
    import uvicorn
    
    await log_info(
        f"Запуск Trip Service на порту {settings.deployment.TRIP_SERVICE_PORT}...",
        type_msg=TypeMsg.INFO
    )
    
    config = uvicorn.Config(
        "src.services.trips.app:app",
        host="0.0.0.0",
        port=settings.deployment.TRIP_SERVICE_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        await log_info("Trip Service: graceful shutdown", type_msg=TypeMsg.DEBUG)
        await server.shutdown()


async def run_pricing_service() -> None:
    """Запускает Pricing Service (расчёт тарифов, конвертация в Stars)."""
    import uvicorn
    
    await log_info(
        f"Запуск Pricing Service на порту {settings.deployment.PRICING_SERVICE_PORT}...",
        type_msg=TypeMsg.INFO
    )
    
    config = uvicorn.Config(
        "src.services.pricing.app:app",
        host="0.0.0.0",
        port=settings.deployment.PRICING_SERVICE_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        await log_info("Pricing Service: graceful shutdown", type_msg=TypeMsg.DEBUG)
        await server.shutdown()


# === Микросервисы Phase 2: Gateways ===

async def run_payments_service() -> None:
    """Запускает Payments Service (Telegram Stars, балансы, выводы)."""
    import uvicorn
    
    await log_info(
        f"Запуск Payments Service на порту {settings.deployment.PAYMENTS_SERVICE_PORT}...",
        type_msg=TypeMsg.INFO
    )
    
    config = uvicorn.Config(
        "src.services.payments.app:app",
        host="0.0.0.0",
        port=settings.deployment.PAYMENTS_SERVICE_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        await log_info("Payments Service: graceful shutdown", type_msg=TypeMsg.DEBUG)
        await server.shutdown()


async def run_miniapp_bff() -> None:
    """Запускает MiniApp BFF (Backend for Frontend для React Mini App)."""
    import uvicorn
    
    await log_info(
        f"Запуск MiniApp BFF на порту {settings.deployment.MINIAPP_BFF_PORT}...",
        type_msg=TypeMsg.INFO
    )
    
    config = uvicorn.Config(
        "src.services.miniapp_bff.app:app",
        host="0.0.0.0",
        port=settings.deployment.MINIAPP_BFF_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        await log_info("MiniApp BFF: graceful shutdown", type_msg=TypeMsg.DEBUG)
        await server.shutdown()


# === Микросервисы Phase 3: Realtime ===

async def run_realtime_ws_gateway() -> None:
    """Запускает Realtime WebSocket Gateway (live-tracking, подписки)."""
    import uvicorn
    
    await log_info(
        f"Запуск Realtime WebSocket Gateway на порту {settings.deployment.REALTIME_WS_GATEWAY_PORT}...",
        type_msg=TypeMsg.INFO
    )
    
    config = uvicorn.Config(
        "src.services.realtime_ws.app:app",
        host="0.0.0.0",
        port=settings.deployment.REALTIME_WS_GATEWAY_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        await log_info("Realtime WS Gateway: graceful shutdown", type_msg=TypeMsg.DEBUG)
        await server.shutdown()


async def run_realtime_location_ingest() -> None:
    """Запускает Realtime Location Ingest (приём координат, GEO индекс)."""
    import uvicorn
    
    await log_info(
        f"Запуск Realtime Location Ingest на порту {settings.deployment.REALTIME_LOCATION_INGEST_PORT}...",
        type_msg=TypeMsg.INFO
    )
    
    config = uvicorn.Config(
        "src.services.realtime_location.app:app",
        host="0.0.0.0",
        port=settings.deployment.REALTIME_LOCATION_INGEST_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        await log_info("Realtime Location Ingest: graceful shutdown", type_msg=TypeMsg.DEBUG)
        await server.shutdown()


async def run_order_matching_service() -> None:
    """Запускает Order Matching Service (диспетчеризация, поиск водителей)."""
    import uvicorn
    
    await log_info(
        f"Запуск Order Matching Service на порту {settings.deployment.ORDER_MATCHING_SERVICE_PORT}...",
        type_msg=TypeMsg.INFO
    )
    
    config = uvicorn.Config(
        "src.services.order_matching.app:app",
        host="0.0.0.0",
        port=settings.deployment.ORDER_MATCHING_SERVICE_PORT,
        reload=settings.system.DEBUG,
        log_level="debug" if settings.system.DEBUG else "info",
    )
    
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except asyncio.CancelledError:
        await log_info("Order Matching Service: graceful shutdown", type_msg=TypeMsg.DEBUG)
        await server.shutdown()


async def run_postgres() -> None:
    """Запускает только PostgreSQL (для локальной разработки)."""
    await log_info("PostgreSQL должен быть запущен через Docker", type_msg=TypeMsg.WARNING)
    await log_info("Используйте: ./manage_docker.sh up postgres", type_msg=TypeMsg.INFO)


async def run_redis() -> None:
    """Запускает только Redis (для локальной разработки)."""
    await log_info("Redis должен быть запущен через Docker", type_msg=TypeMsg.WARNING)
    await log_info("Используйте: ./manage_docker.sh up redis", type_msg=TypeMsg.INFO)


async def run_rabbitmq() -> None:
    """Запускает только RabbitMQ (для локальной разработки)."""
    await log_info("RabbitMQ должен быть запущен через Docker", type_msg=TypeMsg.WARNING)
    await log_info("Используйте: ./manage_docker.sh up rabbitmq", type_msg=TypeMsg.INFO)


def interactive_mode_selection() -> str:
    """
    Интерактивный выбор режима запуска.
    
    Returns:
        Выбранный режим
    """
    print("\n" + "="*80)
    print("  TAXI BOT v0.5.2 — Выбор компонента для запуска")
    print("="*80)
    print("\n🔵 Legacy компоненты:")
    print("  1.  bot                    — Telegram Bot (основной бот)")
    print("  2.  web_admin              — Web Admin UI (панель администратора)")
    print("  3.  web_client             — Web Client UI (клиентский интерфейс)")
    print("  4.  notifications          — Notifications Service (HTTP API)")
    print("  5.  matching_worker        — MatchingWorker (deprecated, используй 18)")
    print("\n🟢 Микросервисы Phase 1 — Core Services:")
    print("  11. users_service          — Users Service (:8084)")
    print("  12. trip_service           — Trip Service (:8085)")
    print("  13. pricing_service        — Pricing Service (:8086)")
    print("\n🟡 Микросервисы Phase 2 — Gateways:")
    print("  14. payments_service       — Payments Service (:8087)")
    print("  15. miniapp_bff            — MiniApp BFF (:8088)")
    print("\n🟠 Микросервисы Phase 3 — Realtime:")
    print("  16. realtime_ws            — Realtime WebSocket Gateway (:8089)")
    print("  17. realtime_location      — Realtime Location Ingest (:8090)")
    print("  18. order_matching         — Order Matching Service (:8091)")
    print("\n🚀 Комплексный запуск:")
    print("  20. all                    — Все legacy компоненты одновременно")
    print("  21. microservices          — Все 8 микросервисов одновременно")
    print("  22. everything             — Все компоненты (legacy + микросервисы)")
    print("\n⚙️  Инфраструктура (только через Docker):")
    print("  30. postgres               — PostgreSQL (через Docker)")
    print("  31. redis                  — Redis (через Docker)")
    print("  32. rabbitmq               — RabbitMQ (через Docker)")
    print("\n" + "="*80)
    
    mode_map = {
        "1": "bot",
        "2": "web_admin",
        "3": "web_client",
        "4": "notifications",
        "5": "matching_worker",
        "11": "users_service",
        "12": "trip_service",
        "13": "pricing_service",
        "14": "payments_service",
        "15": "miniapp_bff",
        "16": "realtime_ws",
        "17": "realtime_location",
        "18": "order_matching",
        "20": "all",
        "21": "microservices",
        "22": "everything",
        "30": "postgres",
        "31": "redis",
        "32": "rabbitmq",
    }
    
    # Для обратной совместимости
    valid_modes = (set(mode_map.values()) | set(mode_map.keys()) | 
                   {"web", "worker"})
    
    while True:
        choice = input("\nВыберите компонент (номер или название): ").strip().lower()
        
        if choice in mode_map:
            return mode_map[choice]
        elif choice in valid_modes:
            return choice
        else:
            print("❌ Неверный выбор. Попробуйте снова.")


async def main(mode: str | None = None) -> None:
    """
    Главная функция запуска.
    
    Args:
        mode: Режим запуска (bot, web, worker, all). 
              Если None, определяется из настроек или интерактивно.
    """
    global _running_tasks
    
    setup_logging()
    setup_signal_handlers()
    
    # Определяем режим запуска
    if mode is None:
        # Проверяем RUN_DEV_MODE
        if settings.system.RUN_DEV_MODE:
            # Режим разработчика: запускаем все компоненты
            mode = "all"
            await log_info(
                "🔧 RUN_DEV_MODE включен — запуск всех legacy компонентов",
                type_msg=TypeMsg.INFO
            )
        else:
            # Проверяем переменную окружения COMPONENT_MODE (для Docker)
            component_mode = settings.system.COMPONENT_MODE
            valid_modes = (
                "bot", "web", "web_admin", "web_client", "notifications", 
                "matching_worker", "worker",
                "users_service", "trip_service", "pricing_service",
                "payments_service", "miniapp_bff",
                "realtime_ws", "realtime_location", "order_matching",
                "postgres", "redis", "rabbitmq",
                "all", "microservices", "everything"
            )
            if component_mode and component_mode in valid_modes:
                mode = component_mode
                await log_info(
                    f"🐳 Docker режим — запуск компонента '{mode}'",
                    type_msg=TypeMsg.INFO
                )
            else:
                # Интерактивный выбор
                mode = interactive_mode_selection()
    
    await log_info(
        f"Taxi Bot v{settings.system.VERSION} — запуск в режиме '{mode}'",
        type_msg=TypeMsg.INFO
    )
    
    try:
        # Сначала инициализируем инфраструктуру (критично для работы приложения и тестов)
        await init_infrastructure()
        await warmup_cache()
        
        # Запуск тестов при старте, если включено в конфиге (ПОСЛЕ инициализации)
        run_tests_flag = settings.system.RUN_TESTS_ON_STARTUP
        await log_info(f"RUN_TESTS_ON_STARTUP = {run_tests_flag}", type_msg=TypeMsg.DEBUG)
        
        if run_tests_flag:
            await log_info("Запуск тестов (инфраструктура уже инициализирована)...", type_msg=TypeMsg.INFO)
            tests_passed = await run_tests()
            if not tests_passed:
                await log_error("❌ Тесты не прошли. Остановка запуска приложения.")
                await close_infrastructure()
                sys.exit(1)
        else:
            await log_info("Пропуск запуска тестов (RUN_TESTS_ON_STARTUP=false)", type_msg=TypeMsg.DEBUG)
        
        # === Legacy компоненты ===
        if mode == "bot":
            await run_bot()
        elif mode == "web":
            await run_web()  # Обратная совместимость
        elif mode == "web_admin":
            await run_web_admin()
        elif mode == "web_client":
            await run_web_client()
        elif mode == "notifications":
            await run_notifications()
        elif mode == "matching_worker" or mode == "worker":  # worker для обратной совместимости
            await run_matching_worker()
        
        # === Микросервисы Phase 1: Core Services ===
        elif mode == "users_service":
            await run_users_service()
        elif mode == "trip_service":
            await run_trip_service()
        elif mode == "pricing_service":
            await run_pricing_service()
        
        # === Микросервисы Phase 2: Gateways ===
        elif mode == "payments_service":
            await run_payments_service()
        elif mode == "miniapp_bff":
            await run_miniapp_bff()
        
        # === Микросервисы Phase 3: Realtime ===
        elif mode == "realtime_ws":
            await run_realtime_ws_gateway()
        elif mode == "realtime_location":
            await run_realtime_location_ingest()
        elif mode == "order_matching":
            await run_order_matching_service()
        
        # === Инфраструктура ===
        elif mode == "postgres":
            await run_postgres()
        elif mode == "redis":
            await run_redis()
        elif mode == "rabbitmq":
            await run_rabbitmq()
        
        # === Комплексный запуск ===
        elif mode == "all":
            # Параллельный запуск всех компонентов
            # Важно: при RUN_DEV_MODE=true инфраструктура уже инициализирована выше
            await log_info("Запуск всех компонентов параллельно (RUN_DEV_MODE)...", type_msg=TypeMsg.INFO)
            
            global _running_tasks
            # Создаем задачи для асинхронных компонентов
            bot_task = asyncio.create_task(run_bot())
            worker_task = asyncio.create_task(run_matching_worker())
            _running_tasks = [bot_task, worker_task]
            
            try:
                # Запускаем асинхронные компоненты с return_exceptions для корректной отмены
                await asyncio.gather(
                    bot_task,
                    worker_task,
                    return_exceptions=True,
                    # Web и Notifications запускаются отдельно из-за blocking event loop
                    # Они должны быть запущены в отдельных процессах/контейнерах
                )
            except asyncio.CancelledError:
                await log_info("Отмена всех задач...", type_msg=TypeMsg.INFO)
                # Отменяем все задачи
                for task in _running_tasks:
                    if not task.done():
                        task.cancel()
                # Ждем завершения отмены
                await asyncio.gather(*_running_tasks, return_exceptions=True)
                raise
            
            # Примечание: в режиме RUN_DEV_MODE рекомендуется использовать Docker Compose
            # для запуска Web Admin, Web Client и Notifications в отдельных контейнерах
        
        elif mode == "microservices":
            # Запуск всех 8 микросервисов параллельно
            await log_info(
                "Запуск всех микросервисов (8 сервисов: users, trips, pricing, payments, miniapp_bff, realtime_ws, realtime_location, order_matching)...",
                type_msg=TypeMsg.INFO
            )
            
            _running_tasks = [
                asyncio.create_task(run_users_service()),
                asyncio.create_task(run_trip_service()),
                asyncio.create_task(run_pricing_service()),
                asyncio.create_task(run_payments_service()),
                asyncio.create_task(run_miniapp_bff()),
                asyncio.create_task(run_realtime_ws_gateway()),
                asyncio.create_task(run_realtime_location_ingest()),
                asyncio.create_task(run_order_matching_service()),
            ]
            
            try:
                await asyncio.gather(*_running_tasks, return_exceptions=True)
            except asyncio.CancelledError:
                await log_info("Отмена всех микросервисов...", type_msg=TypeMsg.INFO)
                for task in _running_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*_running_tasks, return_exceptions=True)
                raise
        
        elif mode == "everything":
            # Запуск ВСЕХ компонентов (legacy + микросервисы)
            await log_info(
                "Запуск ВСЕХ компонентов (legacy + 8 микросервисов)...",
                type_msg=TypeMsg.INFO
            )
            
            _running_tasks = [
                # Legacy
                asyncio.create_task(run_bot()),
                asyncio.create_task(run_matching_worker()),
                # Микросервисы
                asyncio.create_task(run_users_service()),
                asyncio.create_task(run_trip_service()),
                asyncio.create_task(run_pricing_service()),
                asyncio.create_task(run_payments_service()),
                asyncio.create_task(run_miniapp_bff()),
                asyncio.create_task(run_realtime_ws_gateway()),
                asyncio.create_task(run_realtime_location_ingest()),
                asyncio.create_task(run_order_matching_service()),
            ]
            
            try:
                await asyncio.gather(*_running_tasks, return_exceptions=True)
            except asyncio.CancelledError:
                await log_info("Отмена всех компонентов...", type_msg=TypeMsg.INFO)
                for task in _running_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*_running_tasks, return_exceptions=True)
                raise
            
            # Примечание: Web компоненты (web_admin, web_client, notifications)
            # должны быть запущены в отдельных процессах/контейнерах
        
        else:
            await log_error(f"Неизвестный режим: {mode}")
            
    except KeyboardInterrupt:
        await log_info("Получен сигнал остановки (Ctrl+C)", type_msg=TypeMsg.INFO)
    except asyncio.CancelledError:
        await log_info("Задача отменена, выполняется graceful shutdown", type_msg=TypeMsg.INFO)
    except Exception as e:
        await log_error(f"Критическая ошибка: {e}")
        raise
    finally:
        # Отменяем все оставшиеся задачи
        if _running_tasks:
            await log_info("Отмена оставшихся задач...", type_msg=TypeMsg.DEBUG)
            for task in _running_tasks:
                if not task.done():
                    task.cancel()
            # Ждем завершения всех задач
            await asyncio.gather(*_running_tasks, return_exceptions=True)
            _running_tasks.clear()
        
        await log_info("Завершение работы, закрытие подключений...", type_msg=TypeMsg.INFO)
        try:
            await close_infrastructure()
        except Exception as e:
            await log_error(f"Ошибка при закрытии подключений: {e}")
        await log_info("Приложение остановлено", type_msg=TypeMsg.INFO)


def print_usage() -> None:
    """Выводит справку по использованию."""
    print("""
Taxi Bot v0.5.2 — Микросервисная архитектура для такси-сервиса

Использование:
    python main.py [mode]

🔵 Legacy компоненты:
    bot                    — Telegram Bot
    web_admin              — Web Admin UI (панель администратора)
    web_client             — Web Client UI (клиентский интерфейс)
    notifications          — Notifications Service (HTTP API)
    matching_worker        — MatchingWorker (deprecated, используй order_matching)

🟢 Микросервисы Phase 1 — Core Services:
    users_service          — Users Service (:8084)
    trip_service           — Trip Service (:8085)
    pricing_service        — Pricing Service (:8086)

🟡 Микросервисы Phase 2 — Gateways:
    payments_service       — Payments Service (:8087)
    miniapp_bff            — MiniApp BFF (:8088)

🟠 Микросервисы Phase 3 — Realtime:
    realtime_ws            — Realtime WebSocket Gateway (:8089)
    realtime_location      — Realtime Location Ingest (:8090)
    order_matching         — Order Matching Service (:8091)

🚀 Комплексный запуск:
    all                    — Все legacy компоненты
    microservices          — Все 8 микросервисов
    everything             — Все компоненты (legacy + микросервисы)
    
⚙️  Инфраструктура (только через Docker):
    postgres               — PostgreSQL database
    redis                  — Redis cache
    rabbitmq               — RabbitMQ message broker

Примеры:
    python main.py                       # Автоматический режим
    python main.py bot                   # Только Telegram Bot
    python main.py users_service         # Только Users Service
    python main.py microservices         # Все микросервисы
    python main.py everything            # Все компоненты
    
Docker:
    docker-compose -f docker-compose.infra.yml -f docker-compose.services.yml up -d
    """)


if __name__ == "__main__":
    # Определяем режим из аргументов командной строки
    mode = None  # Будет определен автоматически в main()
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--help", "-h"):
            print_usage()
            sys.exit(0)
        elif arg in (
            # Legacy
            "bot", "web", "web_admin", "web_client", "notifications", 
            "matching_worker", "worker",
            # Микросервисы
            "users_service", "trip_service", "pricing_service",
            "payments_service", "miniapp_bff",
            "realtime_ws", "realtime_location", "order_matching",
            # Инфраструктура
            "postgres", "redis", "rabbitmq",
            # Комплексный запуск
            "all", "microservices", "everything"
        ):
            mode = arg
        else:
            print(f"Ошибка: неизвестный режим '{arg}'")
            print_usage()
            sys.exit(1)
    
    try:
        asyncio.run(main(mode))
    except KeyboardInterrupt:
        pass
