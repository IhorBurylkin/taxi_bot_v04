# src/services/miniapp_bff/telegram_auth.py
"""
Валидация Telegram Mini App initData.
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, unquote

from pydantic import BaseModel


class TelegramUser(BaseModel):
    """Данные пользователя из initData."""
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool | None = None
    photo_url: str | None = None


class TelegramInitData(BaseModel):
    """Распарсенные данные initData."""
    user: TelegramUser
    auth_date: datetime
    query_id: str | None = None
    chat_type: str | None = None
    chat_instance: str | None = None
    start_param: str | None = None
    hash: str


class TelegramAuthError(Exception):
    """Ошибка валидации Telegram данных."""
    pass


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,  # 24 часа
) -> TelegramInitData:
    """
    Валидировать initData от Telegram Mini App.
    
    Args:
        init_data: URL-encoded строка от Telegram WebApp.init_data
        bot_token: Токен бота
        max_age_seconds: Максимальный возраст данных (по умолчанию 24 часа)
    
    Returns:
        TelegramInitData с данными пользователя
    
    Raises:
        TelegramAuthError: Если данные невалидны или устарели
    """
    try:
        # Парсим URL-encoded данные
        parsed = parse_qs(init_data)
        
        # Извлекаем хэш
        if "hash" not in parsed:
            raise TelegramAuthError("Отсутствует hash в initData")
        
        received_hash = parsed["hash"][0]
        
        # Формируем строку для проверки (без hash, отсортировано по ключам)
        data_check_pairs = []
        for key in sorted(parsed.keys()):
            if key != "hash":
                value = parsed[key][0]
                data_check_pairs.append(f"{key}={value}")
        
        data_check_string = "\n".join(data_check_pairs)
        
        # Вычисляем секретный ключ: HMAC-SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256,
        ).digest()
        
        # Вычисляем хэш данных
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        # Сравниваем хэши
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise TelegramAuthError("Невалидный hash initData")
        
        # Проверяем возраст данных
        if "auth_date" not in parsed:
            raise TelegramAuthError("Отсутствует auth_date в initData")
        
        auth_date = datetime.fromtimestamp(int(parsed["auth_date"][0]))
        if datetime.utcnow() - auth_date > timedelta(seconds=max_age_seconds):
            raise TelegramAuthError("initData устарели")
        
        # Парсим данные пользователя
        if "user" not in parsed:
            raise TelegramAuthError("Отсутствует user в initData")
        
        user_data = json.loads(unquote(parsed["user"][0]))
        user = TelegramUser(**user_data)
        
        return TelegramInitData(
            user=user,
            auth_date=auth_date,
            query_id=parsed.get("query_id", [None])[0],
            chat_type=parsed.get("chat_type", [None])[0],
            chat_instance=parsed.get("chat_instance", [None])[0],
            start_param=parsed.get("start_param", [None])[0],
            hash=received_hash,
        )
        
    except TelegramAuthError:
        raise
    except Exception as e:
        raise TelegramAuthError(f"Ошибка парсинга initData: {e}")


def extract_user_id(init_data: str) -> int | None:
    """
    Быстрое извлечение user_id из initData без полной валидации.
    Используется для логирования и кэширования.
    """
    try:
        parsed = parse_qs(init_data)
        if "user" in parsed:
            user_data = json.loads(unquote(parsed["user"][0]))
            return user_data.get("id")
    except Exception:
        pass
    return None
