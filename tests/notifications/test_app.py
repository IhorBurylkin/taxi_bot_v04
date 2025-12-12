import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from src.notifications.app import app

client = TestClient(app)

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

def test_health_check(mock_settings):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "notifications",
        "version": "1.0.0"
    }

def test_send_telegram_notification(mock_settings):
    payload = {
        "user_id": 123,
        "message": "Test message",
        "parse_mode": "HTML",
        "disable_notification": False
    }
    
    response = client.post("/api/notify/telegram", json=payload)
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["user_id"] == 123

def test_send_email_notification(mock_settings):
    payload = {
        "email": "test@example.com",
        "subject": "Test",
        "body": "Body"
    }
    
    response = client.post("/api/notify/email", json=payload)
    
    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"

def test_send_push_notification(mock_settings):
    payload = {
        "user_id": 123,
        "title": "Title",
        "body": "Body"
    }
    
    response = client.post("/api/notify/push", json=payload)
    
    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"
