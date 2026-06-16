"""MathModelPro 主入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import tasks, chat, progress, preview, skills, settings, knowledge
from app.api.router import v2_router
from app.services.redis_manager import redis_manager
from app.models.database import init_db

app = FastAPI(
    title="MathModelPro",
    description="AI 驱动的数学建模助手",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.on_event("startup")
async def startup():
    """应用启动"""
    print("MathModelPro starting...")

    # 数据库迁移（Alembic）
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("Database migrated (Alembic)")
    except Exception as e:
        print(f"[WARN] Database migration failed: {e}")
        try:
            init_db()
            print("Database initialized (fallback)")
        except Exception as e2:
            print(f"[WARN] Database init fallback failed: {e2}")

    # 连接 Redis（失败降级到内存模式）
    try:
        await redis_manager.connect()
        print("Redis connected")
    except Exception as e:
        print(f"[WARN] Redis connection failed (will use in-memory): {e}")

    # 初始化 RAG 引擎
    try:
        await knowledge.init_rag_engine()
        print("RAG engine initialized")
    except Exception as e:
        print(f"[WARN] RAG init failed: {e}")

    print("MathModelPro started")


@app.on_event("shutdown")
async def shutdown():
    """应用关闭"""
    try:
        await redis_manager.disconnect()
    except Exception as e:
        print(f"[WARN] Redis disconnect error: {e}")
    print("MathModelPro stopped")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── V1 API（旧架构，稳定运行）─────────────────────────
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(progress.router, prefix="/api/v1", tags=["progress"])
app.include_router(preview.router, prefix="/api/v1", tags=["preview"])
app.include_router(skills.router, prefix="/api/v1", tags=["skills"])
app.include_router(settings.router, prefix="/api/v1", tags=["settings"])
app.include_router(knowledge.router)

# ── V2 API（新架构，渐进迁移）─────────────────────────
app.include_router(v2_router)

# ── 全局异常处理 ─────────────────────────────────────
from app.errors import AppError
from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=400,
        content={"error": exc.code, "message": exc.message, "detail": exc.detail},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "NOT_FOUND", "message": "资源不存在"},
    )


# 健康检查
@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "MathModelPro", "version": "2.0"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")
