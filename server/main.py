"""TowerBells search API and web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from server.db import get_filter_facets, get_filter_options, get_location_facets, get_site, search_sites
from server.settings import ADMIN_ENABLED

if ADMIN_ENABLED:
    from server.editor import admin_search, get_editable_site, update_site_records

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"

app = FastAPI(title="TowerBells Explorer", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _html_page(filename: str) -> FileResponse:
    return FileResponse(
        STATIC_DIR / filename,
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/config")
def public_config() -> dict:
    return {"admin_enabled": ADMIN_ENABLED}


@app.get("/")
def index() -> FileResponse:
    return _html_page("index.html")


@app.get("/carillon/{site_id}")
def carillon_page(site_id: str) -> FileResponse:
    return _html_page("detail.html")


if ADMIN_ENABLED:

    @app.get("/admin")
    def admin_page() -> FileResponse:
        return _html_page("admin.html")

    class SiteUpdatePayload(BaseModel):
        index_fields: dict = {}
        site_fields: dict = {}
        apply_to_milestones: bool = False

    @app.get("/api/admin/search")
    def admin_site_search(q: str = "", limit: int = Query(default=50, le=200)) -> list:
        return admin_search(q, limit=limit)

    @app.get("/api/admin/sites/{site_id}")
    def admin_site_detail(site_id: str) -> dict:
        data = get_editable_site(site_id)
        if not data:
            raise HTTPException(status_code=404, detail="not_found")
        return data

    @app.put("/api/admin/sites/{site_id}")
    def admin_site_update(site_id: str, payload: SiteUpdatePayload) -> dict:
        try:
            return update_site_records(
                site_id,
                index_fields=payload.index_fields,
                site_fields=payload.site_fields,
                apply_to_milestones=payload.apply_to_milestones,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/filters")
def filters() -> dict:
    return get_filter_options()


def _parse_year_event_types(raw: str | None) -> list[str] | None:
    if raw is None or raw == "":
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def _search_query_params(
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    year_event_types: str | None = None,
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
        year_event_types=_parse_year_event_types(year_event_types),
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
    year_event_types: str | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
) -> dict:
    return get_filter_facets(**_search_query_params(
        q, continent, country, state, year_min, year_max, year_event_types,
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
    year_event_types: str | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
) -> dict:
    return get_location_facets(**_search_query_params(
        q, continent, country, state, year_min, year_max, year_event_types,
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
    year_event_types: str | None = None,
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
        year_event_types=_parse_year_event_types(year_event_types),
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
