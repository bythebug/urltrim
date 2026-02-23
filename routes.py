from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from db import get_db
from link_service import create_link, get_by_code
from rate_limit import check_rate_limit
from redis_client import get_redis
from mq import publish_click
from config import settings

router = APIRouter()


class ShortenRequest(BaseModel):
    url: HttpUrl
    alias: str | None = None


class ShortenResponse(BaseModel):
    short_code: str
    long_url: str
    short_url: str


@router.post("/shorten", response_model=ShortenResponse)
async def shorten(
    body: ShortenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    redis = await get_redis()
    client = request.client.host if request.client else "unknown"
    if not await check_rate_limit(redis, f"shorten:{client}"):
        raise HTTPException(status_code=429, detail="too many requests")
    # Treat Swagger's default "string" (or empty string) as no alias -> random code
    alias = body.alias
    if alias in ("", "string"):
        alias = None
    try:
        link = await create_link(db, str(body.url), alias)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=409, detail="alias already taken")
    base = request.base_url
    short_url = f"{base}{link.short_code}"
    return ShortenResponse(
        short_code=link.short_code,
        long_url=link.long_url,
        short_url=short_url,
    )


@router.get("/analytics/{code}")
async def analytics(code: str, db: AsyncSession = Depends(get_db)):
    link = await get_by_code(db, code.lower())
    if not link:
        raise HTTPException(status_code=404, detail="not found")
    return {"short_code": link.short_code, "clicks": link.clicks}


# redirect: high-QPS path. Cache in Redis, publish click async.
@router.get("/{code}", response_class=RedirectResponse)
async def redirect(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    redis = await get_redis()
    cache_key = f"url:{code.lower()}"
    cached = await redis.get(cache_key)
    if cached:
        await publish_click(code.lower())
        return RedirectResponse(url=cached, status_code=302)
    link = await get_by_code(db, code.lower())
    if not link:
        raise HTTPException(status_code=404, detail="not found")
    await redis.setex(cache_key, settings.cache_ttl, link.long_url)
    await publish_click(code.lower())
    return RedirectResponse(url=link.long_url, status_code=302)
