from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.settings import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Candle(Base):
    __tablename__ = "candles"

    timestamp = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String(20), primary_key=True, nullable=False)
    timeframe = Column(String(10), primary_key=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False, default=0)
    spread = Column(Float)


class Tick(Base):
    __tablename__ = "ticks"

    timestamp = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String(20), primary_key=True, nullable=False)
    bid = Column(Float, nullable=False)
    ask = Column(Float, nullable=False)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(50), nullable=False)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    side = Column(String(4), nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True))
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    volume = Column(Float, nullable=False)
    pnl = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    exit_reason = Column(String(20))
    created_at = Column(DateTime(timezone=True), nullable=False)


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
