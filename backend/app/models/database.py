"""数据库模型"""

from datetime import datetime
from typing import Optional, List
from pathlib import Path
from sqlalchemy import Column, String, DateTime, Text, JSON, Integer, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app._paths import db_path as _db_path

Base = declarative_base()

# 数据库 URL（使用绝对路径，避免工作目录变化导致的问题）
DB_PATH = Path(_db_path())
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 创建引擎
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TaskDB(Base):
    """任务表"""
    __tablename__ = "tasks"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    problem_text = Column(Text, default="")
    language = Column(String(20), default="python")
    template_id = Column(String(100), default="cumcm")
    
    status = Column(String(20), default="pending")  # pending/running/completed/failed/cancelled
    
    progress = Column(JSON, default={
        "analysis": 0, "modeling": 0, "coding": 0, "paper": 0, "overall": 0
    })
    
    agent_status = Column(JSON, default={
        "coordinator": "idle", "modeler": "idle", "coder": "idle", "writer": "idle"
    })
    
    token_usage = Column(JSON, default={
        "coordinator": 0, "modeler": 0, "coder": 0, "writer": 0, "total": 0
    })
    
    paper_content = Column(Text, nullable=True)
    code = Column(Text, nullable=True)
    figures = Column(JSON, default=[])
    literature = Column(JSON, default=[])  # 文献检索结果
    notes = Column(Text, default="", nullable=True)  # 用户特殊要求
    checkpoint = Column(JSON, default={})  # 断点续传检查点：{completed_stages, current_stage, partial_result}

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class SkillDB(Base):
    """Skill 表"""
    __tablename__ = "skills"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    agent_type = Column(String(50), nullable=False)  # coordinator/modeler/coder/writer/all
    system_prompt = Column(Text, nullable=False)
    tools = Column(JSON, default=[])
    config = Column(JSON, default={})
    is_builtin = Column(String(1), default="0")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SettingDB(Base):
    """设置表"""
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class LiteratureDB(Base):
    """独立文献表 — 跨任务复用，DOI 去重"""
    __tablename__ = "literature"

    id = Column(String(36), primary_key=True)
    title = Column(String(500), nullable=False)
    authors = Column(JSON, default=[])  # ["Author 1", "Author 2"]
    year = Column(Integer, nullable=True)
    abstract = Column(Text, default="")
    doi = Column(String(200), default="", index=True)  # DOI 去重
    url = Column(String(500), default="")
    journal = Column(String(300), default="")
    citation_count = Column(Integer, default=0)
    source = Column(String(50), default="openalex")  # openalex / tavily / manual
    search_query = Column(String(300), default="")  # 搜索词（历史记录）
    task_id = Column(String(36), nullable=True, index=True)  # 关联任务
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
    # 兼容性迁移：为已有数据库添加新列（幂等安全）
    _add_column_if_not_exists(engine, "tasks", "notes", "TEXT DEFAULT ''")
    _add_column_if_not_exists(engine, "tasks", "checkpoint", "TEXT DEFAULT '{}'")


def _add_column_if_not_exists(engine, table, column, col_def):
    """安全地为 SQLite 表添加列（幂等操作）"""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"PRAGMA table_info({table})"))
            col_names = [row[1] for row in result]
            if column not in col_names:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                conn.commit()
    except Exception:
        pass


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
