import redis.asyncio as redis
from config import settings

_pool: redis.ConnectionPool | None = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    return redis.Redis(connection_pool=_pool)


async def close_redis():
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
