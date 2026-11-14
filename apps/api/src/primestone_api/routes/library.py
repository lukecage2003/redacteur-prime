"""Routes de la Comic Library (/api/v1/library)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import Engine, text

from primestone.comic import ImportSource, LibraryService
from primestone.storage import ObjectNotFoundError

router = APIRouter(prefix="/library", tags=["library"])

MAX_FILES_PER_REQUEST = 200


class ImportItemOut(BaseModel):
    filename: str
    outcome: str
    document_id: UUID | None
    error: str | None


class ImportOut(BaseModel):
    run_id: UUID
    items: list[ImportItemOut]


class DocumentOut(BaseModel):
    id: UUID
    comic_id: UUID
    title: str
    original_filename: str
    format: str | None
    status: str
    page_count: int | None
    expected_page_count: int | None
    pages_rendered: int
    error: str | None


class PageOut(BaseModel):
    number: int
    status: str
    width: int | None
    height: int | None
    error: str | None


class DocumentDetailOut(DocumentOut):
    pages: list[PageOut]


def _service(request: Request) -> LibraryService:
    service: LibraryService = request.app.state.library
    return service


def _engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


@router.post("/imports", status_code=status.HTTP_202_ACCEPTED, response_model=ImportOut)
def create_import(
    request: Request,
    files: Annotated[list[UploadFile], File(description="Fichiers PDF ou CBZ")],
    label: Annotated[str | None, Query(max_length=200)] = None,
) -> ImportOut:
    """Importe un lot. Le traitement (validation, rendu) est asynchrone : suivre le lot via
    `GET /library/imports/{run_id}`."""
    if not files:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "aucun fichier")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"{MAX_FILES_PER_REQUEST} fichiers maximum par requête",
        )
    service = _service(request)
    with tempfile.TemporaryDirectory(prefix="primestone-upload-") as tmp:
        sources = []
        for index, upload in enumerate(files):
            name = Path(upload.filename or f"fichier-{index}").name  # jamais de chemin client
            target = Path(tmp) / f"{index:04d}"
            with target.open("wb") as out:
                shutil.copyfileobj(upload.file, out, length=1024 * 1024)
            sources.append(ImportSource(path=target, filename=name))
        result = service.start_import(sources, label=label)
    return ImportOut(
        run_id=result.run_id,
        items=[
            ImportItemOut(
                filename=i.filename, outcome=i.outcome, document_id=i.document_id, error=i.error
            )
            for i in result.items
        ],
    )


@router.get("/imports/{run_id}")
def get_import(request: Request, run_id: UUID) -> dict[str, Any]:
    report = _service(request).batch_report(run_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "lot introuvable")
    return report


_DOCUMENT_SELECT = """
    SELECT d.id, d.comic_id, c.title, d.original_filename, d.format, d.status, d.page_count,
           c.expected_page_count, d.error,
           (SELECT count(*) FROM page p
             WHERE p.document_id = d.id AND p.status = 'RENDERED') AS pages_rendered
      FROM document d JOIN comic c ON c.id = d.comic_id
"""


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[DocumentOut]:
    sql = _DOCUMENT_SELECT
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status_filter:
        sql += " WHERE d.status = :status"
        params["status"] = status_filter
    sql += " ORDER BY d.created_at DESC, d.id LIMIT :limit OFFSET :offset"
    with _engine(request).connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [DocumentOut.model_validate(dict(r)) for r in rows]


@router.get("/documents/{document_id}", response_model=DocumentDetailOut)
def get_document(request: Request, document_id: UUID) -> DocumentDetailOut:
    with _engine(request).connect() as conn:
        row = (
            conn.execute(text(_DOCUMENT_SELECT + " WHERE d.id = :id"), {"id": document_id})
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "document introuvable")
        pages = (
            conn.execute(
                text(
                    "SELECT number, status, width, height, error FROM page "
                    "WHERE document_id = :id ORDER BY number"
                ),
                {"id": document_id},
            )
            .mappings()
            .all()
        )
    return DocumentDetailOut.model_validate({**dict(row), "pages": [dict(p) for p in pages]})


@router.get(
    "/documents/{document_id}/pages/{number}/image",
    responses={200: {"content": {"image/webp": {}}}, 404: {}},
    response_class=Response,
)
def get_page_image(request: Request, document_id: UUID, number: int) -> Response:
    with _engine(request).connect() as conn:
        key = conn.execute(
            text(
                "SELECT render_key FROM page WHERE document_id = :id AND number = :n "
                "AND status = 'RENDERED'"
            ),
            {"id": document_id, "n": number},
        ).scalar_one_or_none()
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "page non rendue")
    try:
        with request.app.state.store.open(key) as fh:
            data = fh.read()
    except ObjectNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rendu introuvable") from None
    return Response(
        content=data,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )
