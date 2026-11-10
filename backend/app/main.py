from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.assistant.router import router as assistant_router
from app.core.config import settings
from app.planning.router import router as planning_router

app = FastAPI(
    title="LunarSight API",
    version=settings.app_version,
    description="API nền tảng cho dữ liệu, visibility và mission windows của LunarSight.",
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
