from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from json import dumps, loads


def _secret(bot_token, access_password):
    # The web process may start before Mongo-backed settings are imported. The
    # bot token is shared by both processes and already provides a strong key.
    return sha256(f"{bot_token}|starfall-file-link-v1".encode()).digest()


def create_file_token(chat_id, message_id, expires, bot_token, access_password):
    payload = urlsafe_b64encode(dumps(
        {"c": int(chat_id), "m": int(message_id), "e": int(expires)},
        separators=(",", ":"),
    ).encode()).decode().rstrip("=")
    signature = hmac_new(_secret(bot_token, access_password), payload.encode(), sha256).hexdigest()
    return f"{payload}.{signature}"


def decode_file_token(token, now, bot_token, access_password):
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac_new(_secret(bot_token, access_password), payload.encode(), sha256).hexdigest()
        if not compare_digest(signature, expected):
            return None
        raw = payload + "=" * (-len(payload) % 4)
        data = loads(urlsafe_b64decode(raw).decode())
        if int(data["e"]) < int(now):
            return None
        return int(data["c"]), int(data["m"]), int(data["e"])
    except (KeyError, TypeError, ValueError):
        return None
