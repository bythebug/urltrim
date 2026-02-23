import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Link
from short_code import generate_short_code


def _valid_alias(alias: str | None) -> bool:
    if not alias or len(alias) > settings.alias_max_length:
        return False
    return bool(re.match(r"^[a-zA-Z0-9\-]+$", alias))


async def create_link(db: AsyncSession, long_url: str, alias: str | None = None) -> Link:
    if alias and not _valid_alias(alias):
        raise ValueError("invalid alias")
    short_code = alias.strip().lower() if alias else generate_short_code()
    link = Link(long_url=long_url, short_code=short_code, alias=short_code if alias else None)
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link


async def get_by_code(db: AsyncSession, code: str) -> Link | None:
    result = await db.execute(select(Link).where(Link.short_code == code.lower()))
    return result.scalar_one_or_none()


async def increment_clicks(db: AsyncSession, short_code: str) -> None:
    result = await db.execute(select(Link).where(Link.short_code == short_code))
    link = result.scalar_one_or_none()
    if link:
        link.clicks += 1
        await db.flush()
