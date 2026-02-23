import time
import redis.asyncio as redis

from config import settings


async def check_rate_limit(redis_client: redis.Redis, key: str) -> bool:
    """Sliding window: allow N requests per minute. Returns True if allowed."""
    now = time.time()
    window = 60
    limit = settings.rate_limit_per_minute
    rkey = f"rl:{key}"
    pipe = redis_client.pipeline()
    pipe.zadd(rkey, {str(now): now})
    pipe.zremrangebyscore(rkey, 0, now - window)
    pipe.zcard(rkey)
    pipe.expire(rkey, window + 1)
    _, _, count, _ = await pipe.execute()
    return count <= limit
