"""FastAPI application bound to loopback by the process entrypoint."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database import (
    VALID_STATUSES,
    get_offer_by_id,
    get_offer_by_url,
    get_profile,
    init_db,
    insert_offer,
    list_offers,
    save_offer_analysis,
    save_profile,
    update_offer_draft,
    update_offer_status,
)
from src.analysis.fit import analyze_fit
from src.api.auth import (
    cookie_name,
    end_session,
    login_allowed,
    record_login_failure,
    require_auth,
    start_session,
    token_matches,
)
from src.api.schemas import LoginRequest, OfferImport, OfferPatch, ProfileUpdate
from src.api.textutil import plain_text

logger = logging.getLogger(__name__)

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)
_AUTH = Depends(require_auth)

auth_router = APIRouter()
api_router = APIRouter(dependencies=[_AUTH])


def _public_offer(row: dict) -> dict:
    """Offer payload for the signed-in user. Resume paths are not on this row."""
    return {
        "id": row["id"],
        "company_name": row.get("company_name") or "",
        "job_title": row.get("job_title") or "",
        "url": row.get("url") or "",
        "ats_type": row.get("ats_type") or "",
        "location": row.get("location") or "",
        "work_modality": row.get("work_modality") or "",
        "status": row.get("status") or "",
        "created_at": row.get("created_at") or "",
        "applied_at": row.get("applied_at") or "",
        "description": plain_text(row.get("description") or "", limit=20000),
        "fit_score": row.get("fit_score"),
        "fit_summary": row.get("fit_summary") or "",
        "gap_notes": row.get("gap_notes") or "",
        "draft_body": row.get("draft_body") or "",
    }


def _public_profile(row: dict) -> dict:
    """Profile for the signed-in user. No filesystem paths."""
    return {
        "full_name": row.get("full_name") or "",
        "email": row.get("email") or "",
        "phone": row.get("phone") or "",
        "origin_sector": row.get("origin_sector") or "",
        "origin_role": row.get("origin_role") or "",
        "origin_years": row.get("origin_years"),
        "origin_highlights": row.get("origin_highlights") or "",
        "target_roles": row.get("target_roles") or "",
        "target_sectors": row.get("target_sectors") or "",
        "seniority": row.get("seniority") or "",
        "constraints_text": row.get("constraints_text") or "",
        "bridge": row.get("bridge") or [],
        "anchors": row.get("anchors") or {},
        "proof": row.get("proof") or [],
        "updated_at": row.get("updated_at") or "",
    }


async def security_headers(request: Request, call_next):
    """Reject oversized bodies and attach a strict browser policy."""
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > 200_000:
        return Response(status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = _CSP
    response.headers["Cache-Control"] = "no-store"
    return response


async def hide_validation_input(_request: Request, _exc: RequestValidationError):
    """Do not reflect request bodies. They can contain the API token."""
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})


@auth_router.post("/api/auth/login")
def login(body: LoginRequest, response: Response) -> dict:
    if not login_allowed():
        raise HTTPException(status_code=429, detail="Too many attempts")
    if not token_matches(body.token):
        record_login_failure()
        raise HTTPException(status_code=401, detail="Authentication required")
    session_id = start_session()
    response.set_cookie(
        key=cookie_name(),
        value=session_id,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=8 * 60 * 60,
        path="/",
    )
    return {"authenticated": True}


@auth_router.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    end_session(request.cookies.get(cookie_name()))
    response.delete_cookie(cookie_name(), path="/")
    return {"authenticated": False}


@api_router.get("/api/me")
def me() -> dict:
    return {"authenticated": True}


@api_router.get("/api/offers")
def offers(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="invalid status")
    rows, total = list_offers(status=status, limit=limit, offset=offset)
    return {"total": total, "items": [_public_offer(row) for row in rows]}


@api_router.post("/api/offers/import", status_code=201)
def offer_import(body: OfferImport) -> dict:
    existing = get_offer_by_url(body.url)
    if existing is not None:
        return _public_offer(existing)
    description = plain_text(body.description or "", limit=20000) or None
    try:
        offer_id = insert_offer(
            company_name=body.company_name,
            job_title=body.job_title,
            url=body.url,
            ats_type=body.ats_type,
            location=body.location,
            description=description,
            status="PENDING",
        )
    except Exception as exc:
        logger.exception("Failed to import offer")
        raise HTTPException(status_code=400, detail="Could not save offer") from exc
    if offer_id is None:
        raise HTTPException(status_code=400, detail="Could not save offer")
    row = get_offer_by_id(offer_id)
    if row is None:
        raise HTTPException(status_code=400, detail="Could not save offer")
    return _public_offer(row)


@api_router.post("/api/offers/{offer_id}/analyze")
def offer_analyze(offer_id: int) -> dict:
    """Score the offer locally. Does not submit an application."""
    row = get_offer_by_id(offer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    result = analyze_fit(get_profile(), row)
    saved = save_offer_analysis(
        offer_id,
        fit_score=result["fit_score"],
        fit_summary=result["fit_summary"],
        gap_notes=result["gap_notes"],
        draft_body=result["draft_body"],
    )
    if not saved:
        raise HTTPException(status_code=404, detail="Not found")
    updated = get_offer_by_id(offer_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Not found")
    payload = _public_offer(updated)
    payload["matched"] = result["matched"]
    payload["gaps"] = result["gaps"]
    return payload


@api_router.get("/api/offers/{offer_id}")
def offer_detail(offer_id: int) -> dict:
    row = get_offer_by_id(offer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _public_offer(row)


@api_router.patch("/api/offers/{offer_id}")
def offer_patch(offer_id: int, body: OfferPatch) -> dict:
    row = get_offer_by_id(offer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if body.status is not None:
        update_offer_status(offer_id, body.status)
    if body.draft_body is not None:
        update_offer_draft(offer_id, body.draft_body)
    updated = get_offer_by_id(offer_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _public_offer(updated)


@api_router.get("/api/profile")
def read_profile() -> dict:
    return _public_profile(get_profile())


@api_router.put("/api/profile")
def write_profile(body: ProfileUpdate) -> dict:
    saved = save_profile(
        {
            **body.model_dump(),
            "bridge": [item.model_dump() for item in body.bridge],
        }
    )
    return _public_profile(saved)


def _mount_frontend(app: FastAPI) -> None:
    index = _FRONTEND_DIR / "index.html"
    if not index.is_file():
        return
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIR), name="assets")

    @app.get("/")
    def dashboard() -> FileResponse:
        return FileResponse(index)


def create_app() -> FastAPI:
    """Build the app. Docs stay off so the surface is only the routes we test."""
    init_db()
    app = FastAPI(title="Looking Jobs", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_exception_handler(RequestValidationError, hide_validation_input)
    app.middleware("http")(security_headers)
    app.include_router(auth_router)
    app.include_router(api_router)
    _mount_frontend(app)
    return app
