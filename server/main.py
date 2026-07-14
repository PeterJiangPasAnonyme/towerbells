"""TowerBells search API and web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.db import get_filter_facets, get_filter_options, get_location_facets, get_site, search_sites

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"

app = FastAPI(title="TowerBells Explorer", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/carillon/{site_id}")
def carillon_page(site_id: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "detail.html")


@app.get("/api/filters")
def filters() -> dict:
    return get_filter_options()


def _search_query_params(
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
) -> dict:
    return dict(
        q=q,
        continent=continent,
        country=country,
        state=state,
        year_min=year_min,
        year_max=year_max,
        bellfounder=bellfounder,
        bourdon_pitch=bourdon_pitch,
        transposition=transposition,
        range_class=range_class,
        denomination=denomination,
        institution_type=institution_type,
        instrument_type=instrument_type,
    )


@app.get("/api/filters/facets")
def filter_facets(
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
) -> dict:
    return get_filter_facets(**_search_query_params(
        q, continent, country, state, year_min, year_max,
        bellfounder, bourdon_pitch, transposition, range_class,
        denomination, institution_type, instrument_type,
    ))


@app.get("/api/filters/location")
def location_filters(
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
) -> dict:
    return get_location_facets(**_search_query_params(
        q, continent, country, state, year_min, year_max,
        bellfounder, bourdon_pitch, transposition, range_class,
        denomination, institution_type, instrument_type,
    ))


@app.get("/api/search")
def search(
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
    map_only: bool = False,
    limit: int = Query(default=5000, le=10000),
) -> dict:
    return search_sites(
        q=q,
        continent=continent,
        country=country,
        state=state,
        year_min=year_min,
        year_max=year_max,
        bellfounder=bellfounder,
        bourdon_pitch=bourdon_pitch,
        transposition=transposition,
        range_class=range_class,
        denomination=denomination,
        institution_type=institution_type,
        instrument_type=instrument_type,
        map_only=map_only,
        limit=limit,
    )


@app.get("/api/sites/{site_id}")
def site_detail(site_id: str) -> dict:
    data = get_site(site_id)
    if not data:
        return {"error": "not_found"}
    return data
