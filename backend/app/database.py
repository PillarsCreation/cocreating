"""数据库配置层：SQLite（演示）/ PostgreSQL（生产）可切换"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 通过环境变量切换数据库，默认使用 SQLite 便于演示
DATABASE_URL = os.getenv("REDGATE_DB_URL", "sqlite:///./redgate.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖注入：每个请求独立会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
