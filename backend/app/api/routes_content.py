"""Operator-only local reference content library."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.connection import get_db
from app.database.models import ReferenceContent
from app.database.operations import Experience
from app.services.briefing_ai import BriefingAIError, analyze_briefing
from app.services.content_matching import derive_points, suggest_review_points, validate_points
from app.services.pdf_import import MAX_PDF_BYTES, PdfImportError, extract_pdf
from app.services.site_import import SiteImportError, import_site

router = APIRouter(prefix="/api/v1/contents", tags=["contents"])


class ContentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=50000)
    language: Literal["pt"] = "pt"
    source: Literal["typed", "txt", "md", "pdf", "url"] = "typed"
    points: list[str] | None = None
    fair_available: bool = False


class UrlInput(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class TextPreviewInput(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


def _view(row):
    return {
        "id": row.id,
        "title": row.title,
        "text": row.text,
        "language": row.language,
        "source": row.source,
        "version": row.version,
        "points": json.loads(row.points_json),
        "fair_available": row.fair_available,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _apply(row, payload):
    if not payload.title.strip() or not payload.text.strip():
        raise HTTPException(422, "Titulo e texto obrigatorios")
    points = payload.points if payload.points is not None else derive_points(payload.text)
    try:
        points = validate_points(payload.text, points)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row.title, row.text, row.language, row.source = (
        payload.title.strip(),
        payload.text.strip(),
        payload.language,
        payload.source,
    )
    row.points_json = json.dumps(points, ensure_ascii=False)
    row.fair_available = payload.fair_available


@router.post("/import-pdf")
async def import_pdf(file: UploadFile = File(...)):
    """Return an editable preview; saving/selecting remains a separate action."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(422, "Selecione um arquivo .pdf.")
    try:
        data = await file.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(413, "PDF excede 5 MB.")
        try:
            return extract_pdf(data)
        except PdfImportError as exc:
            raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()


@router.post("/import-url")
def import_url(payload: UrlInput):
    """Fetch public page text, returning an editable preview only."""
    try:
        return import_site(payload.url)
    except SiteImportError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/prepare-text")
def prepare_text(payload: TextPreviewInput):
    """Suggest verbatim points for pasted prose; no model or remote call."""
    if not payload.text.strip():
        raise HTTPException(422, "Cole um texto antes de preparar o briefing.")
    return {"text": payload.text.strip(), "points": suggest_review_points(payload.text)}


@router.post("/analyze-briefing")
def analyze_reference_briefing(payload: TextPreviewInput):
    try:
        return analyze_briefing(payload.text, get_settings().briefing_model)
    except BriefingAIError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("", status_code=201)
def create_content(payload: ContentInput, db: Session = Depends(get_db)):
    row = ReferenceContent()
    _apply(row, payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _view(row)


@router.get("")
def list_contents(db: Session = Depends(get_db)):
    return [
        {
            "id": row.id,
            "title": row.title,
            "version": row.version,
            "fair_available": row.fair_available,
        }
        for row in db.query(ReferenceContent).order_by(ReferenceContent.id).all()
    ]


@router.get("/{content_id}")
def get_content(content_id: int, db: Session = Depends(get_db)):
    row = db.get(ReferenceContent, content_id)
    if row is None:
        raise HTTPException(404, "Conteudo nao encontrado")
    return _view(row)


@router.put("/{content_id}")
def update_content(content_id: int, payload: ContentInput, db: Session = Depends(get_db)):
    row = db.get(ReferenceContent, content_id)
    if row is None:
        raise HTTPException(404, "Conteudo nao encontrado")
    _apply(row, payload)
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.commit()
    return _view(row)


@router.delete("/{content_id}")
def delete_content(content_id: int, db: Session = Depends(get_db)):
    db.execute(text("BEGIN IMMEDIATE"))
    row = db.get(ReferenceContent, content_id)
    if row is None:
        raise HTTPException(404, "Conteudo nao encontrado")
    db.delete(row)
    experience = db.get(Experience, 1)
    if experience is not None:
        state = json.loads(experience.payload or "{}")
        if state.get("selected_content_id") == content_id:
            state["selected_content_id"] = None
            experience.payload = json.dumps(state, ensure_ascii=False)
    db.commit()
    return {"deleted": True}
