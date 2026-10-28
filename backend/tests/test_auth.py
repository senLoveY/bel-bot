import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from app.auth import validate_init_data

TOKEN = "123456:TEST"


def make_init_data(token=TOKEN, auth_date=None, user=None):
    data = {
        "auth_date": str(auth_date or int(time.time())),
        "user": json.dumps(user or {"id": 42, "first_name": "Ala"}),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_valid_init_data():
    assert validate_init_data(make_init_data(), TOKEN)["id"] == 42


def test_wrong_token_rejected():
    assert validate_init_data(make_init_data(token="999:OTHER"), TOKEN) is None


def test_tampered_rejected():
    tampered = make_init_data().replace("Ala", "Eve")
    assert validate_init_data(tampered, TOKEN) is None


def test_expired_rejected():
    old = make_init_data(auth_date=int(time.time()) - 3 * 24 * 3600)
    assert validate_init_data(old, TOKEN) is None


def test_garbage_rejected():
    assert validate_init_data("", TOKEN) is None
    assert validate_init_data("hash=abc", TOKEN) is None
