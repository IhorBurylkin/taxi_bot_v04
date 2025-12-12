import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User, Chat, Location
from aiogram.fsm.context import FSMContext

from src.bot.handlers.passenger import (
    start_new_order,
    receive_pickup_location,
    receive_pickup_address,
    receive_destination_location,
    receive_destination_address,
    confirm_order,
    cancel_order,
)
from src.bot.states import OrderStates
from src.common.constants import PaymentMethod

@pytest.fixture
def mock_message():
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 123
    message.text = "test_text"
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
    callback.data = "test_data"
    callback.answer = AsyncMock()
    return callback

@pytest.fixture
def mock_state():
    state = AsyncMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.clear = AsyncMock()
    return state

@pytest.mark.asyncio
async def test_start_new_order_success(mock_callback, mock_state):
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service, \
         patch("src.bot.handlers.passenger.get_order_service") as mock_get_order_service:
        
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=MagicMock(language="ru"))
        
        order_service = mock_get_order_service.return_value
        order_service.get_active_order_for_passenger = AsyncMock(return_value=None)
        
        await start_new_order(mock_callback, mock_state)
        
        mock_state.set_state.assert_called_once_with(OrderStates.pickup_location)
        mock_callback.message.edit_text.assert_called_once()

@pytest.mark.asyncio
async def test_start_new_order_user_not_found(mock_callback, mock_state):
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service:
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=None)
        
        await start_new_order(mock_callback, mock_state)
        
        # Expecting error message about registration
        mock_callback.answer.assert_called()

@pytest.mark.asyncio
async def test_start_new_order_active_order(mock_callback, mock_state):
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service, \
         patch("src.bot.handlers.passenger.get_order_service") as mock_get_order_service:
        
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=MagicMock(language="ru"))
        
        order_service = mock_get_order_service.return_value
        order_service.get_active_order_for_passenger = AsyncMock(return_value=MagicMock())
        
        await start_new_order(mock_callback, mock_state)
        
        mock_callback.answer.assert_called_with("У вас уже есть активный заказ")

@pytest.mark.asyncio
async def test_receive_pickup_location_success(mock_message, mock_state):
    mock_message.location = Location(latitude=55.75, longitude=37.61)
    
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service, \
         patch("src.bot.handlers.passenger.get_geo_service") as mock_get_geo_service:
        
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=MagicMock(language="ru"))
        
        geo_service = mock_get_geo_service.return_value
        geo_service.reverse_geocode = AsyncMock(return_value="Moscow, Red Square")
        
        await receive_pickup_location(mock_message, mock_state)
        
        mock_state.update_data.assert_called_once()
        mock_state.set_state.assert_called_once_with(OrderStates.destination_location)
        mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_receive_pickup_address_success(mock_message, mock_state):
    mock_message.text = "Red Square"
    
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service, \
         patch("src.bot.handlers.passenger.get_geo_service") as mock_get_geo_service:
        
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=MagicMock(language="ru"))
        
        geo_service = mock_get_geo_service.return_value
        geo_service.geocode = AsyncMock(return_value=MagicMock(latitude=55.75, longitude=37.61, address="Moscow, Red Square"))
        
        await receive_pickup_address(mock_message, mock_state)
        
        mock_state.update_data.assert_called_once()
        mock_state.set_state.assert_called_once_with(OrderStates.destination_location)
        mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_receive_destination_location_success(mock_message, mock_state):
    mock_message.location = Location(latitude=55.76, longitude=37.62)
    mock_state.get_data.return_value = {"pickup_lat": 55.75, "pickup_lng": 37.61}
    
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service, \
         patch("src.bot.handlers.passenger.get_geo_service") as mock_get_geo_service, \
         patch("src.bot.handlers.passenger.get_order_service") as mock_get_order_service:
        
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=MagicMock(language="ru"))
        
        geo_service = mock_get_geo_service.return_value
        geo_service.reverse_geocode = AsyncMock(return_value="Moscow, Tverskaya")
        geo_service.calculate_route = AsyncMock(return_value=MagicMock(distance_km=2.0, duration_minutes=10))
        
        order_service = mock_get_order_service.return_value
        order_service.calculate_fare = MagicMock(return_value=MagicMock(total_fare=200, currency="RUB"))
        
        await receive_destination_location(mock_message, mock_state)
        
        mock_state.update_data.assert_called()
        mock_state.set_state.assert_called_once_with(OrderStates.confirm)
        mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_receive_destination_address_success(mock_message, mock_state):
    mock_message.text = "Tverskaya"
    mock_state.get_data.return_value = {"pickup_lat": 55.75, "pickup_lng": 37.61}
    
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service, \
         patch("src.bot.handlers.passenger.get_geo_service") as mock_get_geo_service, \
         patch("src.bot.handlers.passenger.get_order_service") as mock_get_order_service:
        
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=MagicMock(language="ru"))
        
        geo_service = mock_get_geo_service.return_value
        geo_service.geocode = AsyncMock(return_value=MagicMock(latitude=55.76, longitude=37.62, address="Moscow, Tverskaya"))
        geo_service.calculate_route = AsyncMock(return_value=MagicMock(distance_km=2.0, duration_minutes=10))
        
        order_service = mock_get_order_service.return_value
        order_service.calculate_fare = MagicMock(return_value=MagicMock(total_fare=200, currency="RUB"))
        
        await receive_destination_address(mock_message, mock_state)
        
        mock_state.update_data.assert_called()
        mock_state.set_state.assert_called_once_with(OrderStates.confirm)
        mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_confirm_order_success(mock_callback, mock_state):
    mock_state.get_data.return_value = {
        "pickup_address": "A", "pickup_lat": 1.0, "pickup_lng": 1.0,
        "dest_address": "B", "dest_lat": 2.0, "dest_lng": 2.0,
        "distance_km": 5.0, "duration_min": 15
    }
    
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service, \
         patch("src.bot.handlers.passenger.get_order_service") as mock_get_order_service:
        
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=MagicMock(language="ru"))
        
        order_service = mock_get_order_service.return_value
        order_service.create_order = AsyncMock(return_value=MagicMock(id="1"))
        order_service.start_search = AsyncMock()
        
        await confirm_order(mock_callback, mock_state)
        
        order_service.create_order.assert_called_once()
        order_service.start_search.assert_called_once_with("1")
        mock_state.clear.assert_called_once()
        mock_callback.message.edit_text.assert_called_once()

@pytest.mark.asyncio
async def test_cancel_order_success(mock_callback, mock_state):
    with patch("src.bot.handlers.passenger.get_user_service") as mock_get_user_service, \
         patch("src.bot.handlers.passenger.get_order_service") as mock_get_order_service:
        
        user_service = mock_get_user_service.return_value
        user_service.get_user = AsyncMock(return_value=MagicMock(language="ru"))
        
        order_service = mock_get_order_service.return_value
        order_service.get_active_order_for_passenger = AsyncMock(return_value=MagicMock(id="1"))
        order_service.cancel_order = AsyncMock()
        
        await cancel_order(mock_callback, mock_state)
        
        order_service.cancel_order.assert_called_once_with("1", "passenger")
        mock_state.clear.assert_called_once()
        mock_callback.message.edit_text.assert_called_once()
