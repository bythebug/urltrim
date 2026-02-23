from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from db import engine, Base
from redis_client import get_redis, close_redis
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)
app.include_router(router, tags=["links"])


@app.get("/")
async def root():
    return {"service": "urltrim", "docs": "/docs"}
