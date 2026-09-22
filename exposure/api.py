"""FastAPI app. Thin: validation and status codes only, the numbers come from
exposure.service."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse

from exposure.service import RANKING, AssetAmbiguous, AssetNotFound, build_index

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PACKAGE_DIR.parent / "data"
STATIC_INDEX = PACKAGE_DIR / "static" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    data_dir = Path(os.environ.get("EXPOSURE_DATA_DIR", DEFAULT_DATA_DIR))
    app.state.index = build_index(data_dir)
    yield


app = FastAPI(title="Envira exposure service", lifespan=lifespan)


@app.get("/")
def root():
    if STATIC_INDEX.is_file():
        return FileResponse(STATIC_INDEX)
    return {"service": app.title, "docs": "/docs"}


@app.get("/health")
def health(request: Request):
    return {"status": "ok", **request.app.state.index.summary()}


@app.get("/assets/{asset_id}/exposure")
def asset_exposure(asset_id: str, request: Request):
    try:
        return request.app.state.index.exposure(asset_id)
    except AssetNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except AssetAmbiguous as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@app.get("/portfolio/exposure")
def portfolio_exposure(
    request: Request,
    asset_type: str | None = None,
    ids: list[str] | None = Query(None, description="Comma separated and/or repeated"),
):
    index = request.app.state.index
    id_list = [part.strip() for value in (ids or []) for part in value.split(",") if part.strip()]
    if (asset_type is None) == (not id_list):
        raise HTTPException(status_code=400, detail="give exactly one of asset_type or ids")
    if asset_type is not None and asset_type not in index.asset_types:
        raise HTTPException(
            status_code=400,
            detail=f"unknown asset_type {asset_type}; valid types: {', '.join(index.asset_types)}",
        )
    result = index.portfolio(asset_type=asset_type, ids=id_list or None)
    return {"count": len(result["assets"]), "ranking": RANKING, **result}
