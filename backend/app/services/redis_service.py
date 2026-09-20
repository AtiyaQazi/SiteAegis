import json
from typing import Any

from app.core.redis import redis_manager


MONITORING_TTL_SECONDS = 300


def cache_latest_monitoring_update(
    site_id: int,
    payload: dict[str, Any],
) -> bool:
    """
    Store the latest monitoring update for a site in Redis.

    Redis is used as a fast cache for the latest state.
    PostgreSQL remains the permanent source of truth.
    """

    key = f"siteaegis:monitoring:site:{site_id}:latest"

    try:
        value = json.dumps(
            payload,
            default=str,
        )

        return redis_manager.set(
            key=key,
            value=value,
            expire=MONITORING_TTL_SECONDS,
        )

    except Exception as exc:
        print(
            f"[REDIS ERROR] Could not cache monitoring "
            f"update for site #{site_id}: {exc}"
        )
        return False


def get_latest_monitoring_update(
    site_id: int,
) -> dict[str, Any] | None:
    """
    Read the latest monitoring update for a site from Redis.
    """

    key = f"siteaegis:monitoring:site:{site_id}:latest"

    try:
        value = redis_manager.get(key)

        if value is None:
            return None

        return json.loads(value)

    except Exception as exc:
        print(
            f"[REDIS ERROR] Could not read monitoring "
            f"cache for site #{site_id}: {exc}"
        )
        return None


def delete_latest_monitoring_update(
    site_id: int,
) -> bool:
    """
    Remove a site's latest monitoring cache.
    """

    key = f"siteaegis:monitoring:site:{site_id}:latest"

    try:
        return redis_manager.delete(key)

    except Exception as exc:
        print(
            f"[REDIS ERROR] Could not delete monitoring "
            f"cache for site #{site_id}: {exc}"
        )
        return False