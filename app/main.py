"""Montagem da aplicação: API em /api, interface React servida como arquivos estáticos."""
from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import router
from .api_viagens import router as viagens_router
from .api_receitas import router as receitas_router
from .db import init_db

@asynccontextmanager
async def lifespan(_: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="Orçamento ESR", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
METODOS_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def protecoes(request: Request, call_next):
    # defesa extra contra CSRF: escrita só se a origem for o próprio site
    if request.method in METODOS_ESCRITA:
        origem = request.headers.get("origin") or request.headers.get("referer")
        if origem:
            host = urlparse(origem).netloc
            if host != request.headers.get("host", ""):
                return JSONResponse({"detail": "Origem não permitida."}, status_code=403)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/api"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


app.include_router(router)
app.include_router(viagens_router)
app.include_router(receitas_router)

if config.WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str):
        if caminho.startswith("api/"):
            return JSONResponse({"detail": "Não encontrado."}, status_code=404)
        arq = (config.WEB_DIST / caminho).resolve()
        if caminho and arq.is_file() and config.WEB_DIST.resolve() in arq.parents:
            return FileResponse(arq)
        return FileResponse(config.WEB_DIST / "index.html")
