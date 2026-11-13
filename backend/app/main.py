from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.assistant.router import router as assistant_router
from app.assistant.config import get_assistant_settings
from app.core.config import settings
from app.planning.router import router as planning_router
from app.point_analysis.router import router as point_analysis_router
from app.services.lunarsight.imagery import ImageryCache, router as imagery_router

@asynccontextmanager
async def lifespan(application: FastAPI):
    assistant = get_assistant_settings()
    timeout = httpx.Timeout(connect=assistant.assistant_connect_timeout_seconds,
                             read=None, write=None, pool=None)
    limits = httpx.Limits(max_connections=16, max_keepalive_connections=8)
    application.state.llm_clients = {
        "nvidia": httpx.AsyncClient(timeout=timeout, limits=limits),
        "gemini": httpx.AsyncClient(timeout=timeout, limits=limits),
        "openai": httpx.AsyncClient(timeout=timeout, limits=limits),
    }
    imagery_client = httpx.AsyncClient(timeout=httpx.Timeout(25, connect=10),
                                     limits=httpx.Limits(max_connections=6), follow_redirects=False)
    application.state.imagery = ImageryCache(imagery_client)
    try:
        yield
    finally:
        await imagery_client.aclose()
        for client in application.state.llm_clients.values():
            await client.aclose()
        from app.point_analysis.horizon_preload import get_horizon_preloads
        if get_horizon_preloads.cache_info().currsize:
            get_horizon_preloads().close()
            get_horizon_preloads.cache_clear()


app = FastAPI(
    title="HOSA API",
    version=settings.app_version,
    description="API nền tảng cho dữ liệu, visibility và mission windows của HOSA.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")

app.include_router(assistant_router, prefix="/api")

app.include_router(planning_router, prefix="/api")
app.include_router(point_analysis_router, prefix="/api")
app.include_router(imagery_router, prefix="/api")
