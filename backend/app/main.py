"""FastAPI application factory."""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, games, health, matchmaking, users
from app.core.config import Settings, get_settings
from app.realtime import endpoint
from app.realtime.commands import GameCommands
from app.realtime.connections import ConnectionManager
from app.realtime.sweeper import Sweeper

API_PREFIX = "/api/v1"


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run the timeout sweeper for as long as the application is serving."""
    task = asyncio.create_task(Sweeper(app.state.commands, app.state.settings).run())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.commands = GameCommands(ConnectionManager())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(endpoint.router)

    api_router = APIRouter(prefix=API_PREFIX)
    api_router.include_router(auth.router)
    api_router.include_router(users.router)
    api_router.include_router(matchmaking.router)
    api_router.include_router(games.router)
    app.include_router(api_router)

    return app


app = create_app()
