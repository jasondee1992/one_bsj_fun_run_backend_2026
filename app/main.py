from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.init_db import init_db
from app.routers import admin, auth, payments, registrations


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(registrations.router, prefix="/api")
    app.include_router(payments.router, prefix="/api")
    app.include_router(admin.router, prefix="/api/admin")

    @app.get("/api/health")
    def health_check() -> dict:
        return {"success": True, "message": "API is healthy", "data": {"status": "ok"}}

    return app


app = create_app()
