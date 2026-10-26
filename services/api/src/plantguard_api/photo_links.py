from __future__ import annotations

import hashlib
import hmac
import time


class PhotoLinkSigner:
    def __init__(self, signing_key: str) -> None:
        self._signing_key = signing_key.encode()

    def sign(self, method: str, storage_key: str, expires: int) -> str:
        payload = self._payload(method, storage_key, expires)
        return hmac.new(self._signing_key, payload, hashlib.sha256).hexdigest()

    def verify(
        self,
        method: str,
        storage_key: str,
        expires: int,
        signature: str,
        *,
        now: int | None = None,
    ) -> bool:
        current_time = int(time.time()) if now is None else now
        if expires < current_time:
            return False
        expected = self.sign(method, storage_key, expires)
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def _payload(method: str, storage_key: str, expires: int) -> bytes:
        return f"{method.upper()}\n{storage_key}\n{expires}".encode()
