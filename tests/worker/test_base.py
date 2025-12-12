# tests/worker/test_base.py
"""
Unit тесты для базового класса воркера (src/worker/base.py).
"""

import asyncio
import pytest
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from src.worker.base import BaseWorker
from src.infra.event_bus import DomainEvent


class ConcreteWorker(BaseWorker):
    """Конкретная реализация воркера для тестирования."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.handled_events: List[DomainEvent] = []

    @property
    def name(self) -> str:
        return "test_worker"

    @property
    def subscriptions(self) -> List[str]:
        return ["test.event.created", "test.event.updated"]

    async def handle_event(self, event: DomainEvent) -> None:
        """Сохраняем обработанное событие для проверки."""
        self.handled_events.append(event)


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Мок шины событий."""
    bus = MagicMock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_db() -> MagicMock:
    """Мок менеджера БД."""
    return MagicMock()


@pytest.fixture
def mock_redis() -> MagicMock:
    """Мок Redis клиента."""
    return MagicMock()


@pytest.fixture
def worker(
    mock_event_bus: MagicMock,
    mock_db: MagicMock,
    mock_redis: MagicMock,
) -> ConcreteWorker:
    """Экземпляр воркера для тестов."""
    return ConcreteWorker(
        event_bus=mock_event_bus,
        db=mock_db,
        redis=mock_redis,
    )


class TestBaseWorkerInitialization:
    """Тесты инициализации воркера."""

    def test_initialization_with_dependencies(
        self,
        mock_event_bus: MagicMock,
        mock_db: MagicMock,
        mock_redis: MagicMock,
    ) -> None:
        """Тест инициализации воркера с зависимостями."""
        worker = ConcreteWorker(
            event_bus=mock_event_bus,
            db=mock_db,
            redis=mock_redis,
        )

        assert worker.event_bus is mock_event_bus
        assert worker.db is mock_db
        assert worker.redis is mock_redis
        assert worker._running is False
        assert worker._tasks == []

    @patch("src.worker.base.get_event_bus")
    @patch("src.worker.base.get_db")
    @patch("src.worker.base.get_redis")
    def test_initialization_without_dependencies(
        self,
        mock_get_redis: MagicMock,
        mock_get_db: MagicMock,
        mock_get_event_bus: MagicMock,
    ) -> None:
        """Тест инициализации воркера без явных зависимостей."""
        mock_bus = MagicMock()
        mock_database = MagicMock()
        mock_redis_client = MagicMock()

        mock_get_event_bus.return_value = mock_bus
        mock_get_db.return_value = mock_database
        mock_get_redis.return_value = mock_redis_client

        worker = ConcreteWorker()

        assert worker.event_bus is mock_bus
        assert worker.db is mock_database
        assert worker.redis is mock_redis_client


class TestBaseWorkerProperties:
    """Тесты свойств воркера."""

    def test_worker_name(self, worker: ConcreteWorker) -> None:
        """Тест свойства name."""
        assert worker.name == "test_worker"

    def test_worker_subscriptions(self, worker: ConcreteWorker) -> None:
        """Тест свойства subscriptions."""
        assert worker.subscriptions == ["test.event.created", "test.event.updated"]


class TestBaseWorkerStart:
    """Тесты запуска воркера."""

    @pytest.mark.asyncio
    async def test_start_worker(
        self,
        worker: ConcreteWorker,
        mock_event_bus: MagicMock,
    ) -> None:
        """Тест запуска воркера."""
        with patch("src.worker.base.log_info", new_callable=AsyncMock):
            await worker.start()

            assert worker._running is True
            
            # Проверяем, что подписались на все события
            assert mock_event_bus.subscribe.call_count == 2
            
            # Проверяем вызовы подписки
            calls = mock_event_bus.subscribe.call_args_list
            assert calls[0][1]["event_type"] == "test.event.created"
            assert calls[1][1]["event_type"] == "test.event.updated"

    @pytest.mark.asyncio
    async def test_start_already_running_worker(
        self,
        worker: ConcreteWorker,
        mock_event_bus: MagicMock,
    ) -> None:
        """Тест повторного запуска уже работающего воркера."""
        with patch("src.worker.base.log_info", new_callable=AsyncMock):
            await worker.start()
            mock_event_bus.subscribe.reset_mock()
            
            # Пытаемся запустить снова
            await worker.start()
            
            # Не должно быть новых подписок
            mock_event_bus.subscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_logs_info(self, worker: ConcreteWorker) -> None:
        """Тест логирования при запуске."""
        with patch("src.worker.base.log_info", new_callable=AsyncMock) as mock_log:
            await worker.start()
            
            # Проверяем, что было логирование
            assert mock_log.call_count >= 3  # Запуск + 2 подписки + завершение


class TestBaseWorkerStop:
    """Тесты остановки воркера."""

    @pytest.mark.asyncio
    async def test_stop_worker(self, worker: ConcreteWorker) -> None:
        """Тест остановки воркера."""
        with patch("src.worker.base.log_info", new_callable=AsyncMock):
            await worker.start()
            await worker.stop()

            assert worker._running is False

    @pytest.mark.asyncio
    async def test_stop_not_running_worker(self, worker: ConcreteWorker) -> None:
        """Тест остановки неработающего воркера."""
        with patch("src.worker.base.log_info", new_callable=AsyncMock) as mock_log:
            await worker.stop()
            
            # Не должно быть логов об остановке
            assert worker._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self, worker: ConcreteWorker) -> None:
        """Тест отмены задач при остановке."""
        with patch("src.worker.base.log_info", new_callable=AsyncMock):
            await worker.start()
            
            # Создаём реальную асинхронную задачу
            async def dummy_task():
                await asyncio.sleep(10)
            
            task = asyncio.create_task(dummy_task())
            worker._tasks.append(task)
            
            await worker.stop()
            
            # Проверяем, что задача была отменена
            assert task.cancelled()


class TestBaseWorkerEventHandling:
    """Тесты обработки событий."""

    @pytest.mark.asyncio
    async def test_on_event_handles_event(self, worker: ConcreteWorker) -> None:
        """Тест обработки события."""
        with patch("src.worker.base.log_info", new_callable=AsyncMock):
            await worker.start()
            
            event = DomainEvent(
                event_type="test.event.created",
                payload={"id": 123, "name": "Test"},
            )
            
            await worker._on_event(event)
            
            # Проверяем, что событие было обработано
            assert len(worker.handled_events) == 1
            assert worker.handled_events[0] is event

    @pytest.mark.asyncio
    async def test_on_event_ignores_when_not_running(
        self,
        worker: ConcreteWorker,
    ) -> None:
        """Тест игнорирования событий, когда воркер не запущен."""
        event = DomainEvent(
            event_type="test.event.created",
            payload={"id": 123},
        )
        
        await worker._on_event(event)
        
        # Событие не должно быть обработано
        assert len(worker.handled_events) == 0

    @pytest.mark.asyncio
    async def test_on_event_handles_exception(
        self,
        worker: ConcreteWorker,
    ) -> None:
        """Тест обработки исключения в handle_event."""
        
        # Переопределяем handle_event для генерации исключения
        async def failing_handle_event(event: DomainEvent) -> None:
            raise ValueError("Test error")
        
        worker.handle_event = failing_handle_event
        
        with patch("src.worker.base.log_info", new_callable=AsyncMock):
            with patch("src.worker.base.log_error", new_callable=AsyncMock) as mock_log_error:
                await worker.start()
                
                event = DomainEvent(
                    event_type="test.event.created",
                    payload={"id": 123},
                )
                
                # Не должно выбросить исключение
                await worker._on_event(event)
                
                # Проверяем, что ошибка была залогирована
                mock_log_error.assert_called_once()
                call_args = mock_log_error.call_args
                assert "Ошибка в воркере" in call_args[0][0]


class TestBaseWorkerIntegration:
    """Интеграционные тесты воркера."""

    @pytest.mark.asyncio
    async def test_full_workflow(
        self,
        mock_event_bus: MagicMock,
        mock_db: MagicMock,
        mock_redis: MagicMock,
    ) -> None:
        """Тест полного цикла работы воркера."""
        worker = ConcreteWorker(
            event_bus=mock_event_bus,
            db=mock_db,
            redis=mock_redis,
        )
        
        with patch("src.worker.base.log_info", new_callable=AsyncMock):
            # Запускаем воркер
            await worker.start()
            assert worker._running is True
            
            # Обрабатываем событие
            event = DomainEvent(
                event_type="test.event.created",
                payload={"id": 123},
            )
            await worker._on_event(event)
            assert len(worker.handled_events) == 1
            
            # Останавливаем воркер
            await worker.stop()
            assert worker._running is False
            
            # После остановки события не обрабатываются
            event2 = DomainEvent(
                event_type="test.event.updated",
                payload={"id": 456},
            )
            await worker._on_event(event2)
            assert len(worker.handled_events) == 1  # Не изменилось
