import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat
from aiogram.fsm.context import FSMContext

from src.bot.handlers.common import cmd_start
from src.core.users.models import User as UserModel

@pytest.fixture
def mock_message():
    message = AsyncMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 123
    message.answer = AsyncMock()
    return message

@pytest.fixture
def mock_state():
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()
    return state

@pytest.fixture
def mock_user_service():
    with patch("src.bot.handlers.common.get_user_service") as mock:
        service = mock.return_value
        service.register_user = AsyncMock()
        service.get_user = AsyncMock()
        yield service

@pytest.fixture
def mock_settings():
    with patch("src.config.settings") as mock:
        mock.logging.LOG_LEVEL = "DEBUG"
        mock.logging.LOG_FORMAT = "colored"
        mock.logging.LOG_TO_FILE = False
        mock.logging.LOG_FILE_PATH = "logs/app.log"
        mock.logging.LOG_MAX_BYTES = 10485760
        mock.logging.LOG_BACKUP_COUNT = 5
        mock.system.ENVIRONMENT = "development"
        yield mock

@pytest.mark.asyncio
async def test_cmd_start_success(mock_message, mock_state, mock_user_service, mock_settings):
    # Mock user registration
    mock_user = UserModel(
        id=123,
        username="testuser",
        first_name="Test",
        last_name="User",
        language="ru"
    )
    mock_user_service.register_user.return_value = mock_user
    
    await cmd_start(mock_message, mock_state)
    
    mock_user_service.register_user.assert_called_once()
    mock_state.clear.assert_called_once()
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_cmd_start_error(mock_message, mock_state, mock_user_service, mock_settings):
    # Mock error
    mock_user_service.register_user.side_effect = Exception("DB Error")
    
    await cmd_start(mock_message, mock_state)
    
    mock_message.answer.assert_called_once()
    # Should send error message
