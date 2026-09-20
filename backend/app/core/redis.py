from typing import Optional

import redis
from redis import Redis

from app.core.config import settings


REDIS_URL = getattr(
    settings,
    "REDIS_URL",
    "redis://127.0.0.1:6379/0",
)


class RedisManager:
    def __init__(self, url: str = REDIS_URL):
        self.url = url
        self.client: Optional[Redis] = None

    def connect(self) -> Redis:
        if self.client is None:
            self.client = redis.Redis.from_url(
                self.url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )

        self.client.ping()
        return self.client

    def ping(self) -> bool:
        try:
            self.connect()
            return True
        except Exception:
            return False

    def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None,
    ) -> bool:
        try:
            client = self.connect()

            return bool(
                client.set(
                    key,
                    value,
                    ex=expire,
                )
            )

        except Exception:
            return False

    def get(self, key: str) -> Optional[str]:
        try:
            client = self.connect()
            return client.get(key)

        except Exception:
            return None

    def delete(self, key: str) -> bool:
        try:
            client = self.connect()
            return bool(client.delete(key))

        except Exception:
            return False

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
            finally:
                self.client = None


redis_manager = RedisManager()