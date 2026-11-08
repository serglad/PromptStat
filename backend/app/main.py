from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import Base, SessionLocal, engine
from .errors import install_error_handlers
from .routers import router_auth, router_connections, router_query


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(bind=engine)
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            from .seed import ensure_encryption_key, seed_demo

            ensure_encryption_key()
            with SessionLocal() as session:
                seed_demo(session)
        yield

    app = FastAPI(title="PromptStat MVP", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    app.include_router(router_auth.router)
    app.include_router(router_connections.router)
    app.include_router(router_query.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    _static_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if _static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str, request: Request):
            candidate = (_static_dir / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(_static_dir.resolve()):
                return FileResponse(candidate)
            return FileResponse(_static_dir / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def root():
            return JSONResponse({"service": "PromptStat MVP", "docs": "/api/docs"})

    return app


app = create_app()
