"""Persistence: farmers, our own mandi price history, and a query log (real usage stats only).

Supabase Postgres in production (HF Spaces disk is wiped on restart); SQLite locally.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import settings


class Base(DeclarativeBase):
    pass


class Farmer(Base):
    __tablename__ = "farmers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    place: Mapped[str] = mapped_column(String(120), default="")
    district: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(120), default="")
    language: Mapped[str] = mapped_column(String(8), default="hi")
    crops: Mapped[list] = mapped_column(JSON, default=list)
    telegram_chat_id: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("date", "market", "commodity", "variety", "grade", name="uq_price_row"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    state: Mapped[str] = mapped_column(String(80), index=True)
    district: Mapped[str] = mapped_column(String(80))
    market: Mapped[str] = mapped_column(String(120))
    commodity: Mapped[str] = mapped_column(String(80), index=True)
    variety: Mapped[str] = mapped_column(String(120), default="")
    grade: Mapped[str] = mapped_column(String(40), default="")
    min_price: Mapped[float] = mapped_column(Float)
    max_price: Mapped[float] = mapped_column(Float)
    modal_price: Mapped[float] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QueryLog(Base):
    __tablename__ = "queries_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8))
    intents: Mapped[list] = mapped_column(JSON, default=list)
    tools_used: Mapped[list] = mapped_column(JSON, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_used: Mapped[str] = mapped_column(String(60), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


LOCAL_SQLITE = f"sqlite:///{Path(__file__).resolve().parent.parent / 'kisansaathi.sqlite3'}"
status = {"backend": "", "warning": ""}  # shown in the UI status panel


@lru_cache
def engine():
    """Supabase Postgres if reachable; otherwise the local SQLite file, so the app never crashes on a DB outage."""
    url = settings().db_url
    try:
        eng = create_engine(url, pool_pre_ping=True, future=True,
                            connect_args={"connect_timeout": 8} if url.startswith("postgresql") else {})
        Base.metadata.create_all(eng)
    except Exception as e:  # noqa: BLE001
        if url == LOCAL_SQLITE:
            raise
        logging.getLogger(__name__).warning("database unreachable (%s); using local SQLite", type(e).__name__)
        status["warning"] = f"Cloud database unreachable ({type(e).__name__}); using local storage"
        eng = create_engine(LOCAL_SQLITE, future=True)
        Base.metadata.create_all(eng)
    status["backend"] = eng.dialect.name
    return eng


def session() -> Session:
    return Session(engine(), expire_on_commit=False)


def upsert_prices(rows: list[dict]) -> int:
    """Insert price rows, ignoring ones we already have (same date/market/commodity/variety/grade)."""
    if not rows:
        return 0
    eng = engine()
    ins = pg_insert if eng.dialect.name == "postgresql" else sqlite_insert
    stmt = ins(PriceHistory).values(rows).on_conflict_do_nothing(
        index_elements=["date", "market", "commodity", "variety", "grade"])
    with eng.begin() as c:
        return c.execute(stmt).rowcount or 0


def price_history(commodity: str, state: str, since: date) -> list[PriceHistory]:
    with session() as s:
        return list(s.scalars(select(PriceHistory).where(
            PriceHistory.commodity == commodity, PriceHistory.state == state,
            PriceHistory.date >= since).order_by(PriceHistory.date)))


def history_span() -> tuple[date | None, date | None, int]:
    with session() as s:
        lo, hi, n = s.execute(select(func.min(PriceHistory.date), func.max(PriceHistory.date),
                                     func.count(PriceHistory.id))).one()
        return lo, hi, n


def log_query(**kw) -> None:
    try:
        with session() as s:
            s.add(QueryLog(**kw))
            s.commit()
    except Exception:  # logging must never break an answer
        pass


def usage_stats() -> dict:
    with session() as s:
        total = s.scalar(select(func.count(QueryLog.id))) or 0
        ver = s.scalar(select(func.count(QueryLog.id)).where(QueryLog.verified.is_(True))) or 0
        farmers = s.scalar(select(func.count(Farmer.id))) or 0
        return {"queries": total, "verified": ver, "farmers": farmers}


# ---- farmer profiles -------------------------------------------------------
def save_farmer(profile) -> int:
    """Insert or update a FarmerProfile; returns its id."""
    data = profile.model_dump(mode="json", exclude={"id"})
    with session() as s:
        row = s.get(Farmer, profile.id) if profile.id else None
        if row is None:
            row = Farmer(**data)
            s.add(row)
        else:
            for k, v in data.items():
                setattr(row, k, v)
        s.commit()
        return row.id


def list_farmers(limit: int = 50) -> list:
    from .models import FarmerProfile
    with session() as s:
        rows = s.scalars(select(Farmer).order_by(Farmer.id.desc()).limit(limit)).all()
        return [FarmerProfile(id=r.id, name=r.name, lat=r.lat, lon=r.lon, place=r.place, district=r.district,
                              state=r.state, language=r.language, crops=r.crops or []) for r in rows]
