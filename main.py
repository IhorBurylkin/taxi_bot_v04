#!/usr/bin/env python3
# main.py
"""
Главная точка входа приложения Taxi Bot.
Запускает Telegram Bot, Web UI или Workers в зависимости от аргументов.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from src.config import settings
from src.common.logger import setup_logging, log_info, log_error
from src.common.constants import TypeMsg
from src.infra.database import init_db, close_db
from src.infra.redis_client import init_redis, close_redis
from src.infra.event_bus import init_event_bus, close_event_bus


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
                    f"✅ Webhook успешно настроен на {settings.telegram.WEBHOOK_URL_MAIN}",
                    type_msg=TypeMsg.INFO,
                )
                await log_info(
                    f"Bot запущен в режиме webhook на {settings.telegram.WEBAPP_HOST}:{settings.telegram.WEBAPP_PORT}",
                    type_msg=TypeMsg.INFO,
                )
                
                # Держим приложение запущенным
                try:
                    await asyncio.Event().wait()
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass
                finally:
                    await runner.cleanup()
                    
            except Exception as e:
                await log_error(f"❌ Не удалось настроить webhook: {e}")
                await log_info("Переключение на режим polling...", type_msg=TypeMsg.INFO)
                
                # Удаляем webhook если не удалось настроить
                try:
                    await remove_webhook(bot)
                except Exception:
                    pass
                
                # Запускаем polling
                await log_info("Bot запущен в режиме polling", type_msg=TypeMsg.INFO)
                await dp.start_polling(bot)
        else:
            # Запуск в режиме polling
            await log_info(
                f"Webhook отключен (USE_WEBHOOK={use_webhook}, WEBHOOK_URL={webhook_url}). "
                f"Запуск в режиме polling",
                type_msg=TypeMsg.INFO
            )
            await dp.start_polling(bot)
            
    finally:
        await bot.session.close()


async def run_web() -> None:
    """Запускает Web UI."""
    from src.web.app import run_web as start_web
    
    await log_info("Запуск Web UI...", type_msg=TypeMsg.INFO)
    start_web(
        host=settings.web.host if hasattr(settings, 'web') else "0.0.0.0",
        port=settings.web.port if hasattr(settings, 'web') else 8080,
    )


async def run_workers() -> None:
    """Запускает воркеры."""
    from src.worker.runner import run_workers as start_workers
    
    await log_info("Запуск Workers...", type_msg=TypeMsg.INFO)
    await start_workers()


async def main(mode: str = "bot") -> None:
    """
    Главная функция запуска.
    
    Args:
        mode: Режим запуска (bot, web, worker, all)
    """
    setup_logging()
    await log_info(f"Taxi Bot v0.1.0 — запуск в режиме '{mode}'", type_msg=TypeMsg.INFO)
    
    try:
        # Запуск тестов при старте, если включено в конфиге
        run_tests_flag = settings.system.RUN_TESTS_ON_STARTUP
        await log_info(f"RUN_TESTS_ON_STARTUP = {run_tests_flag}", type_msg=TypeMsg.DEBUG)
        
        if run_tests_flag:
            tests_passed = await run_tests()
            if not tests_passed:
                await log_error("❌ Тесты не прошли. Остановка запуска приложения.")
                sys.exit(1)
        else:
            await log_info("Пропуск запуска тестов (RUN_TESTS_ON_STARTUP=false)", type_msg=TypeMsg.DEBUG)
        
        await init_infrastructure()
        await warmup_cache()
        
        if mode == "bot":
            await run_bot()
        elif mode == "web":
            await run_web()
        elif mode == "worker":
            await run_workers()
        elif mode == "all":
            # Параллельный запуск всех компонентов
            await asyncio.gather(
                run_bot(),
                run_workers(),
                # Web запускается отдельно из-за blocking event loop
            )
        else:
            await log_error(f"Неизвестный режим: {mode}")
            
    except KeyboardInterrupt:
        await log_info("Получен сигнал остановки (Ctrl+C)", type_msg=TypeMsg.INFO)
    except Exception as e:
        await log_error(f"Критическая ошибка: {e}")
        raise
    finally:
        await close_infrastructure()


def print_usage() -> None:
    """Выводит справку по использованию."""
    print("""
Taxi Bot — Модульный монолит для такси-сервиса

Использование:
    python main.py [mode]

Режимы:
    bot     — Запуск Telegram Bot (по умолчанию)
    web     — Запуск Web Admin UI
    worker  — Запуск фоновых воркеров
    all     — Запуск всех компонентов

Примеры:
    python main.py
    python main.py bot
    python main.py worker
    
Docker:
    docker-compose up -d
    """)


if __name__ == "__main__":
    # Определяем режим из аргументов
    mode = "bot"
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--help", "-h"):
            print_usage()
            sys.exit(0)
        elif arg in ("bot", "web", "worker", "all"):
            mode = arg
        else:
            print(f"Ошибка: неизвестный режим '{arg}'")
            print_usage()
            sys.exit(1)
    
    try:
        asyncio.run(main(mode))
    except KeyboardInterrupt:
        pass
