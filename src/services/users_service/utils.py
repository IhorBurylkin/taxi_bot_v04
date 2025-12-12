import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from typing import Dict, Any, Optional
from src.config import settings

def validate_telegram_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Validates the initData received from Telegram WebApp.
    Returns the parsed data if valid, None otherwise.
    """
    try:
        parsed_data = dict(parse_qsl(init_data))
    except ValueError:
        return None
        
    if "hash" not in parsed_data:
        return None

    hash_check = parsed_data.pop("hash")
    
    # Sort keys alphabetically
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed_data.items())
    )
    
    # Calculate secret key
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256
    ).digest()
    
    # Calculate hash
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if calculated_hash == hash_check:
        # Parse user data if present
        if "user" in parsed_data:
            try:
                parsed_data["user"] = json.loads(parsed_data["user"])
            except json.JSONDecodeError:
                pass
        return parsed_data
    
    return None
