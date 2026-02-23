from sqlalchemy import Column, String, Integer, DateTime, Index
from sqlalchemy.sql import func

from db import Base


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    long_url = Column(String(2048), nullable=False)
    short_code = Column(String(64), nullable=False, unique=True, index=True)
    alias = Column(String(64), unique=True, nullable=True, index=True)
    clicks = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # short_code is the key we use in URLs; alias is optional user-defined
