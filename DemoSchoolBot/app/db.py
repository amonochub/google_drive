from app.config import DB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Boolean

if DB.get("engine") == "sqlite":
    DATABASE_URL = f"sqlite+aiosqlite:///{DB['name']}"
else:
    DATABASE_URL = f"postgresql+asyncpg://{DB['user']}:{DB['password']}@{DB['host']}:{DB['port']}/{DB['name']}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    login = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    tg_id = Column(Integer, unique=True, nullable=True)
    used = Column(Boolean, default=False)
