from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title="LunarSight API",
    version=settings.app_version,
    description="API nền tảng cho dữ liệu, visibility và mission windows của LunarSight.",
)
app.include_router(router, prefix="/api")
