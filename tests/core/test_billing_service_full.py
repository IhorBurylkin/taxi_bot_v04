import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.billing.service import BillingService, PaymentResult, BalanceInfo
from src.common.constants import PaymentMethod, PaymentStatus
from src.infra.event_bus import EventTypes

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
def mock_settings():
    with patch("src.config.settings") as mock:
        mock.stars.PLATFORM_COMMISSION_PERCENT = 20
        mock.stars.STARS_TO_USD_RATE = 0.02
        mock.stars.WITHDRAWAL_MIN_STARS = 500
        
        # Logging settings
        mock.logging.LOG_LEVEL = "DEBUG"
        mock.logging.LOG_FORMAT = "colored"
        mock.logging.LOG_TO_FILE = False
        mock.logging.LOG_FILE_PATH = "logs/app.log"
        mock.logging.LOG_MAX_BYTES = 10485760
        mock.logging.LOG_BACKUP_COUNT = 5
        mock.system.ENVIRONMENT = "test"
        
        yield mock

@pytest.fixture
def billing_service(mock_db, mock_redis, mock_event_bus, mock_settings):
    return BillingService(mock_db, mock_redis, mock_event_bus)

# --- Process Order Payment Tests ---

@pytest.mark.asyncio
async def test_process_order_payment_cash_success(billing_service, mock_db, mock_event_bus):
    mock_db.execute.return_value = None # For insert transaction
    
    result = await billing_service.process_order_payment(
        order_id="order123",
        driver_id=123,
        amount=100.0,
        payment_method=PaymentMethod.CASH
    )
    
    assert result.success is True
    assert result.transaction_id is not None
    
    # Check transaction insert
    mock_db.execute.assert_called_once()
    args = mock_db.execute.call_args[0]
    assert "INSERT INTO transactions" in args[0]
    assert args[4] == 100.0 # amount
    assert args[5] == 20.0 # commission (20%)
    assert args[6] == 80.0 # earnings
    
    # Check event published
    mock_event_bus.publish.assert_called_once()
    event = mock_event_bus.publish.call_args[0][0]
    assert event.event_type == EventTypes.PAYMENT_COMPLETED
    assert event.payload["amount"] == 100.0

@pytest.mark.asyncio
async def test_process_order_payment_card_success(billing_service, mock_db, mock_event_bus):
    mock_db.execute.return_value = None
    
    result = await billing_service.process_order_payment(
        order_id="order123",
        driver_id=123,
        amount=100.0,
        payment_method=PaymentMethod.CARD
    )
    
    assert result.success is True
    
    # Check db calls: 1 insert transaction, 1 update balance
    assert mock_db.execute.call_count == 2
    
    # Check update balance call
    update_call = mock_db.execute.call_args_list[1]
    assert "UPDATE driver_profiles" in update_call[0][0]
    assert update_call[0][2] == 80.0 # earnings added

@pytest.mark.asyncio
async def test_process_order_payment_transaction_fail(billing_service, mock_db, mock_event_bus):
    mock_db.execute.side_effect = Exception("DB Error")
    
    result = await billing_service.process_order_payment(
        order_id="order123",
        driver_id=123,
        amount=100.0,
        payment_method=PaymentMethod.CASH
    )
    
    assert result.success is False
    assert result.error_message == "Не удалось записать транзакцию"

@pytest.mark.asyncio
async def test_process_order_payment_error(billing_service, mock_db, mock_event_bus):
    mock_db.execute.return_value = None
    # Raise exception on first call (PAYMENT_COMPLETED publish fails)
    # Ошибка публикации не должна прерывать транзакцию
    mock_event_bus.publish.side_effect = Exception("Bus Error")
    
    result = await billing_service.process_order_payment(
        order_id="order123",
        driver_id=123,
        amount=100.0,
        payment_method=PaymentMethod.CASH
    )
    
    # Платёж должен быть успешным несмотря на ошибку публикации
    assert result.success is True
    assert result.transaction_id is not None
    
    # Проверяем, что publish был вызван
    assert mock_event_bus.publish.call_count == 1

# --- Get Driver Balance Tests ---

@pytest.mark.asyncio
async def test_get_driver_balance_success(billing_service, mock_db):
    mock_db.fetchrow.return_value = {"balance_stars": 1000}
    
    balance = await billing_service.get_driver_balance(123)
    
    assert balance.stars == 1000
    assert balance.usd_equivalent == 20.0 # 1000 * 0.02
    assert balance.can_withdraw is True # 1000 >= 500

@pytest.mark.asyncio
async def test_get_driver_balance_empty(billing_service, mock_db):
    mock_db.fetchrow.return_value = None
    
    balance = await billing_service.get_driver_balance(123)
    
    assert balance.stars == 0
    assert balance.can_withdraw is False

@pytest.mark.asyncio
async def test_get_driver_balance_error(billing_service, mock_db):
    mock_db.fetchrow.side_effect = Exception("DB Error")
    
    balance = await billing_service.get_driver_balance(123)
    
    assert balance.stars == 0
    assert balance.can_withdraw is False

# --- Add Stars Tests ---

@pytest.mark.asyncio
async def test_add_stars_to_balance_success(billing_service, mock_db):
    mock_db.execute.return_value = None
    
    result = await billing_service.add_stars_to_balance(123, 100)
    
    assert result is True
    mock_db.execute.assert_called_once()
    assert "UPDATE driver_profiles" in mock_db.execute.call_args[0][0]

@pytest.mark.asyncio
async def test_add_stars_to_balance_error(billing_service, mock_db):
    mock_db.execute.side_effect = Exception("DB Error")
    
    result = await billing_service.add_stars_to_balance(123, 100)
    
    assert result is False

# --- Withdraw Stars Tests ---

@pytest.mark.asyncio
async def test_withdraw_stars_success(billing_service, mock_db):
    # Mock get_driver_balance
    mock_db.fetchrow.return_value = {"balance_stars": 1000}
    mock_db.execute.return_value = None
    
    result = await billing_service.withdraw_stars(123, 600)
    
    assert result.success is True
    
    # Check update balance call
    mock_db.execute.assert_called_once()
    assert "UPDATE driver_profiles" in mock_db.execute.call_args[0][0]

@pytest.mark.asyncio
async def test_withdraw_stars_below_min(billing_service):
    result = await billing_service.withdraw_stars(123, 100)
    
    assert result.success is False
    assert "Минимальная сумма" in result.error_message

@pytest.mark.asyncio
async def test_withdraw_stars_insufficient_funds(billing_service, mock_db):
    mock_db.fetchrow.return_value = {"balance_stars": 400} # Less than 600
    
    result = await billing_service.withdraw_stars(123, 600)
    
    assert result.success is False
    assert "Недостаточно средств" in result.error_message

@pytest.mark.asyncio
async def test_withdraw_stars_error(billing_service, mock_db):
    mock_db.fetchrow.return_value = {"balance_stars": 1000}
    mock_db.execute.side_effect = Exception("DB Error")
    
    result = await billing_service.withdraw_stars(123, 600)
    
    assert result.success is False
    assert result.error_message == "DB Error"
