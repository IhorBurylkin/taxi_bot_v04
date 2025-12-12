import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.fsm.context import FSMContext

from src.bot.handlers.common import (
    cmd_start,
    select_passenger_role,
    select_driver_role,
    show_settings,
    change_language,
    go_back,
)
from src.bot.states import RegistrationStates
from src.common.constants import UserRole

@pytest.fixture
def mock_user_service():
    with patch("src.bot.handlers.common.get_user_service") as mock:
        service = AsyncMock()
        mock.return_value = service
        yield service

@pytest.fixture
def mock_message():
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123
    message.from_user.username = "test_user"
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 123
    message.answer = AsyncMock()
    return message

@pytest.fixture
def mock_callback():
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 123
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.data = "test_data"
    return callback

@pytest.fixture
def mock_state():
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    return state

# --- /start Tests ---

@pytest.mark.asyncio
async def test_cmd_start_success(mock_message, mock_state, mock_user_service):
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.register_user.return_value = mock_user
    
    await cmd_start(mock_message, mock_state)
    
    mock_user_service.register_user.assert_called_once()
    mock_state.clear.assert_called_once()
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_cmd_start_fail(mock_message, mock_state, mock_user_service):
    mock_user_service.register_user.return_value = None
    
    await cmd_start(mock_message, mock_state)
    
    mock_message.answer.assert_called_once() # Error message

# --- Role Selection Tests ---

@pytest.mark.asyncio
async def test_select_passenger_role(mock_callback, mock_state, mock_user_service):
    mock_callback.data = "role_passenger"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    await select_passenger_role(mock_callback, mock_state)
    
    mock_user_service.set_user_role.assert_called_once_with(123, UserRole.PASSENGER)
    mock_callback.message.edit_text.assert_called_once()
    mock_callback.answer.assert_called_once()

@pytest.mark.asyncio
async def test_select_driver_role_new(mock_callback, mock_state, mock_user_service):
    mock_callback.data = "role_driver"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_user_service.get_driver_profile.return_value = None
    
    await select_driver_role(mock_callback, mock_state)
    
    mock_state.set_state.assert_called_once_with(RegistrationStates.car_brand)
    mock_callback.message.edit_text.assert_called_once()
    assert "Введите марку" in mock_callback.message.edit_text.call_args[0][0]

@pytest.mark.asyncio
async def test_select_driver_role_existing(mock_callback, mock_state, mock_user_service):
    mock_callback.data = "role_driver"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    mock_profile = MagicMock()
    mock_profile.car_info = "Car Info"
    mock_user_service.get_driver_profile.return_value = mock_profile
    
    await select_driver_role(mock_callback, mock_state)
    
    mock_state.set_state.assert_not_called()
    mock_callback.message.edit_text.assert_called_once()
    assert "Добро пожаловать" in mock_callback.message.edit_text.call_args[0][0]

# --- Settings Tests ---

@pytest.mark.asyncio
async def test_show_settings(mock_callback, mock_user_service):
    mock_callback.data = "settings"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user_service.get_user.return_value = mock_user
    
    await show_settings(mock_callback)
    
    mock_callback.message.edit_text.assert_called_once()
    mock_callback.answer.assert_called_once()

# --- Language Change Tests ---

@pytest.mark.asyncio
async def test_change_language(mock_callback, mock_user_service):
    mock_callback.data = "lang_en"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user.role = UserRole.PASSENGER
    mock_user_service.get_user.return_value = mock_user
    
    await change_language(mock_callback)
    
    assert mock_user.language == "en"
    mock_user_service.update_user.assert_called_once_with(mock_user)
    mock_callback.message.edit_text.assert_called_once()
    mock_callback.answer.assert_called_once()

# --- Back Button Tests ---

@pytest.mark.asyncio
async def test_go_back(mock_callback, mock_state, mock_user_service):
    mock_callback.data = "back"
    
    mock_user = MagicMock()
    mock_user.language = "ru"
    mock_user.role = UserRole.PASSENGER
    mock_user_service.get_user.return_value = mock_user
    
    await go_back(mock_callback, mock_state)
    
    mock_state.clear.assert_called_once()
    mock_callback.message.edit_text.assert_called_once()
    mock_callback.answer.assert_called_once()
