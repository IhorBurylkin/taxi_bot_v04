import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.payments.service import PaymentService
from src.shared.models.payment import PaymentCreateRequest, PaymentMethod, PaymentDTO, PaymentStatus
from src.shared.events.payment_events import PaymentRequested

@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def mock_event_bus():
    return AsyncMock()

@pytest.fixture
def payment_service(mock_db, mock_redis, mock_event_bus):
    return PaymentService(mock_db, mock_redis, mock_event_bus)

@pytest.mark.asyncio
async def test_create_payment(payment_service, mock_event_bus):
    # Arrange
    request = PaymentCreateRequest(
        trip_id="trip-123",
        payer_id=1001,
        payee_id=2002,
        amount=10.0,
        currency="EUR",
        method=PaymentMethod.STARS
    )
    
    # Mock repository methods
    payment_service.repository.save_payment = AsyncMock()
    payment_service.repository.create_payments_table_if_not_exists = AsyncMock()
    
    # Act
    payment = await payment_service.create_payment(request)
    
    # Assert
    assert payment.trip_id == "trip-123"
    assert payment.amount == 10.0
    assert payment.status == PaymentStatus.PENDING
    assert payment.amount_stars is not None # Should be calculated
    
    # Verify DB save
    payment_service.repository.save_payment.assert_called_once()
    
    # Verify Event published
    mock_event_bus.publish.assert_called_once()
    args, _ = mock_event_bus.publish.call_args
    assert args[0] == "payment.requested"
    assert args[1]["trip_id"] == "trip-123"

@pytest.mark.asyncio
async def test_credit_driver_balance(payment_service, mock_redis):
    # Arrange
    driver_id = 2002
    amount_stars = 500
    payment_id = "pay-123"
    
    payment_service.repository.update_balance = AsyncMock()
    payment_service.repository.create_transaction = AsyncMock()
    
    # Act
    await payment_service._credit_driver_balance(driver_id, amount_stars, payment_id)
    
    # Assert
    payment_service.repository.update_balance.assert_called_with(driver_id, float(amount_stars))
    payment_service.repository.create_transaction.assert_called_once()
    mock_redis.delete.assert_called_with(f"driver_balance:{driver_id}")
