from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

redis_sync = Redis.from_url(settings.redis_url, decode_responses=True)
redis_async = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
