"""Agent Server — FastAPI + LangGraph 编排 + 异步队列"""

import logging
import time
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.routes import router as agent_router
from config.settings import get_settings

start_time = time.time()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _setup_langsmith():
    """如果配置了 LangSmith API Key，自动启用追踪"""
    settings = get_settings()
    if settings.LANGSMITH_API_KEY and settings.LANGSMITH_TRACING:
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        os.environ["LANGSMITH_TRACING"] = "true"
        logger.info(f"LangSmith tracing enabled → project: {settings.LANGSMITH_PROJECT}")
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        logger.info("LangSmith tracing disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    from agent.skill_dispatcher import get_dispatcher
    from agent.skills.builtin import register_builtin_skills
    from bridge.workflow_worker import start_workflow_worker, stop_workflow_worker

    settings = get_settings()
    _setup_langsmith()
    register_builtin_skills(get_dispatcher())
    start_workflow_worker()

    logger.info(f"Agent Server starting on {settings.HOST}:{settings.PORT}")
    logger.info(f"Default model: {settings.ANTHROPIC_DEFAULT_MODEL}")
    logger.info(f"Model routing: {settings.MODEL_ROUTING}")

    yield

    await stop_workflow_worker()
    logger.info("Agent Server shutting down...")


app = FastAPI(
    title="Agentic Engineering Server",
    version="3.0.0",
    description="LangGraph-powered multi-agent orchestration with HITL",
    lifespan=lifespan,
)

# CORS — 允许 Electron 渲染进程和本地开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:*",
        "file://",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(agent_router)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": str(exc), "status_code": 500},
    )


@app.get("/")
async def root():
    return {
        "service": "Agentic Engineering Server",
        "version": "3.0.0",
        "uptime_seconds": time.time() - start_time,
        "docs": "/docs",
    }


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, workers=settings.WORKERS)
