import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User, Chat, Location
from aiogram.fsm.context import FSMContext

from src.bot.handlers.driver import (
    receive_car_brand,
    receive_car_model,
    receive_car_color,
    receive_car_plate,
    go_online,
    go_offline,
    update_driver_location,
    accept_order,
    decline_order,
    driver_arrived,
    start_ride,
    complete_ride,
)
from src.bot.states import RegistrationStates, DriverStates
from src.common.constants import UserRole

@pytest.fixture
def mock_user_service():
    with patch("src.bot.handlers.driver.get_user_service") as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service

@pytest.fixture
def mock_order_service():
    with patch("src.bot.handlers.driver.get_order_service") as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service

@pytest.fixture
def mock_matching_service():
    with patch("src.bot.dependencies.get_matching_service") as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service

@pytest.fixture
def mock_message():
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123
    message.from_user.username = "test_driver"
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 123
    message.text = "Test Text"
    message.answer = AsyncMock()
    return message

@pytest.fixture
def mock_callback():
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 123
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()
    callback.data = "test_data"
    return callback

@pytest.fixture
def mock_state():
    state = AsyncMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.clear = AsyncMock()
    return state

# --- Registration Tests ---

@pytest.mark.asyncio
async def test_receive_car_brand(mock_message, mock_state):
    mock_message.text = "Toyota"
    await receive_car_brand(mock_message, mock_state)
    
    mock_state.update_data.assert_called_once_with(car_brand="Toyota")
    mock_state.set_state.assert_called_once_with(RegistrationStates.car_model)
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_receive_car_model(mock_message, mock_state):
    mock_message.text = "Camry"
    await receive_car_model(mock_message, mock_state)
    
    mock_state.update_data.assert_called_once_with(car_model="Camry")
    mock_state.set_state.assert_called_once_with(RegistrationStates.car_color)
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_receive_car_color(mock_message, mock_state):
    mock_message.text = "White"
    await receive_car_color(mock_message, mock_state)
    
    mock_state.update_data.assert_called_once_with(car_color="White")
    mock_state.set_state.assert_called_once_with(RegistrationStates.car_plate)
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_receive_car_plate_success(mock_message, mock_state, mock_user_service):
    mock_message.text = "A123AA77"
    mock_state.get_data.return_value = {
        "car_brand": "Toyota",
        "car_model": "Camry",
        "car_color": "White"
    }
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_profile = MagicMock()
    mock_profile.car_info = "Toyota Camry (A123AA77)"
    mock_user_service.register_driver.return_value = mock_profile
    
    await receive_car_plate(mock_message, mock_state)
    
    mock_user_service.register_driver.assert_called_once()
    mock_state.clear.assert_called_once()
    mock_message.answer.assert_called_once()
    assert "Регистрация завершена" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_receive_car_plate_user_not_found(mock_message, mock_state, mock_user_service):
    mock_user_service.get_user.return_value = None
    await receive_car_plate(mock_message, mock_state)
    mock_message.answer.assert_called_once() # Error message

# --- Status Management Tests ---

@pytest.mark.asyncio
async def test_go_online_success(mock_callback, mock_state, mock_user_service):
    mock_callback.data = "go_online"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_profile = MagicMock()
    mock_profile.is_verified = True
    mock_profile.car_info = "Car Info"
    mock_user_service.get_driver_profile.return_value = mock_profile
    
    mock_user_service.set_driver_online.return_value = True
    
    await go_online(mock_callback, mock_state)
    
    mock_user_service.set_driver_online.assert_called_once_with(123)
    mock_state.set_state.assert_called_once_with(DriverStates.online)
    mock_callback.message.edit_text.assert_called_once()
    assert "Вы на линии" in mock_callback.message.edit_text.call_args[0][0]

@pytest.mark.asyncio
async def test_go_online_not_verified(mock_callback, mock_state, mock_user_service):
    mock_callback.data = "go_online"
    mock_user = MagicMock()
    mock_user_service.get_user.return_value = mock_user
    
    mock_profile = MagicMock()
    mock_profile.is_verified = False
    mock_user_service.get_driver_profile.return_value = mock_profile
    
    await go_online(mock_callback, mock_state)
    
    mock_callback.answer.assert_called_with("Ваш профиль ещё не верифицирован")
    mock_user_service.set_driver_online.assert_not_called()

@pytest.mark.asyncio
async def test_go_offline_success(mock_callback, mock_state, mock_user_service):
    mock_callback.data = "go_offline"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_profile = MagicMock()
    mock_profile.car_info = "Car Info"
    mock_user_service.get_driver_profile.return_value = mock_profile
    
    mock_user_service.set_driver_offline.return_value = True
    
    await go_offline(mock_callback, mock_state)
    
    mock_user_service.set_driver_offline.assert_called_once_with(123)
    mock_state.clear.assert_called_once()
    mock_callback.message.edit_text.assert_called_once()
    assert "Вы ушли с линии" in mock_callback.message.edit_text.call_args[0][0]

# --- Location Update Tests ---

@pytest.mark.asyncio
async def test_update_driver_location(mock_message, mock_state, mock_user_service):
    mock_message.location = Location(latitude=55.75, longitude=37.61)
    
    await update_driver_location(mock_message, mock_state)
    
    mock_user_service.update_driver_location.assert_called_once()
    args = mock_user_service.update_driver_location.call_args[0][0]
    assert args.driver_id == 123
    assert args.latitude == 55.75
    assert args.longitude == 37.61
    mock_message.answer.assert_called_once()

# --- Order Acceptance Tests ---

@pytest.mark.asyncio
async def test_accept_order_success(mock_callback, mock_state, mock_user_service, mock_order_service):
    mock_callback.data = "accept_order_order123"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_order_service.accept_order.return_value = True
    
    mock_order = MagicMock()
    mock_order.pickup_address = "Pickup"
    mock_order.destination_address = "Dest"
    mock_order.estimated_fare = 100
    mock_order_service.get_order.return_value = mock_order
    
    await accept_order(mock_callback, mock_state)
    
    mock_order_service.accept_order.assert_called_once_with("order123", 123)
    mock_state.set_state.assert_called_once_with(DriverStates.on_order)
    mock_state.update_data.assert_called_once_with(order_id="order123")
    mock_callback.message.edit_text.assert_called_once()
    assert "Заказ принят" in mock_callback.message.edit_text.call_args[0][0]

@pytest.mark.asyncio
async def test_accept_order_fail(mock_callback, mock_state, mock_user_service, mock_order_service):
    mock_callback.data = "accept_order_order123"
    mock_user = MagicMock()
    mock_user_service.get_user.return_value = mock_user
    
    mock_order_service.accept_order.return_value = False
    
    await accept_order(mock_callback, mock_state)
    
    mock_callback.answer.assert_any_call("Заказ уже занят или недоступен")

@pytest.mark.asyncio
async def test_decline_order(mock_callback, mock_matching_service):
    mock_callback.data = "decline_order_order123"
    
    # Need to patch get_matching_service inside the handler function scope if it was imported inside
    # But in the code it is imported inside: from src.bot.dependencies import get_matching_service
    # So we need to patch src.bot.handlers.driver.get_matching_service if it was imported at top level
    # OR patch src.bot.dependencies.get_matching_service if it is called directly.
    # The code does: 
    # from src.bot.dependencies import get_matching_service
    # matching_service = get_matching_service()
    # So patching src.bot.dependencies.get_matching_service (which we did in fixture) should work 
    # IF the import happens at runtime inside the function.
    
    await decline_order(mock_callback)
    
    mock_matching_service.mark_driver_rejected.assert_called_once_with("order123", 123)
    mock_callback.message.delete.assert_called_once()
    mock_callback.answer.assert_called_with("Заказ отклонён")

# --- Ride Lifecycle Tests ---

@pytest.mark.asyncio
async def test_driver_arrived(mock_callback, mock_state, mock_user_service, mock_order_service):
    mock_callback.data = "driver_arrived"
    mock_state.get_data.return_value = {"order_id": "order123"}
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_order_service.driver_arrived.return_value = True
    
    await driver_arrived(mock_callback, mock_state)
    
    mock_order_service.driver_arrived.assert_called_once_with("order123")
    mock_callback.message.edit_text.assert_called_once()
    assert "Вы прибыли" in mock_callback.message.edit_text.call_args[0][0]

@pytest.mark.asyncio
async def test_start_ride(mock_callback, mock_state, mock_user_service, mock_order_service):
    mock_callback.data = "start_ride"
    mock_state.get_data.return_value = {"order_id": "order123"}
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_order_service.start_ride.return_value = True
    
    await start_ride(mock_callback, mock_state)
    
    mock_order_service.start_ride.assert_called_once_with("order123")
    mock_callback.message.edit_text.assert_called_once()
    assert "Поездка началась" in mock_callback.message.edit_text.call_args[0][0]

@pytest.mark.asyncio
async def test_complete_ride(mock_callback, mock_state, mock_user_service, mock_order_service):
    mock_callback.data = "complete_ride"
    mock_state.get_data.return_value = {"order_id": "order123"}
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_order = MagicMock()
    mock_order.fare = 150
    mock_order_service.get_order.return_value = mock_order
    
    mock_order_service.complete_order.return_value = True
    
    await complete_ride(mock_callback, mock_state)
    
    mock_order_service.complete_order.assert_called_once_with("order123")
    mock_state.set_state.assert_called_once_with(DriverStates.online)
    mock_state.update_data.assert_called_once_with(order_id=None)
    mock_callback.message.edit_text.assert_called_once()
    assert "Поездка завершена" in mock_callback.message.edit_text.call_args[0][0]
