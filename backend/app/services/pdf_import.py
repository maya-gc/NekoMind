"""Extract reviewable reference text from a small local text-based PDF."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.services.content_matching import terms

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_REFERENCE_CHARS = 50_000


class PdfImportError(ValueError):
    pass


def extract_pdf(data: bytes) -> dict:
    if not data.startswith(b"%PDF-"):
        raise PdfImportError("O arquivo nao e um PDF valido.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise PdfImportError("PDF protegido por senha. Exporte uma copia sem senha.")
        if not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
            raise PdfImportError(f"Use um PDF com ate {MAX_PDF_PAGES} paginas.")
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except PdfImportError:
        raise
    except (PdfReadError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise PdfImportError("Nao foi possivel ler este PDF.") from exc

    # Keep page boundaries for review, but join visual line wraps into sentences.
    text = "\n\n".join(re.sub(r"\s+", " ", page).strip() for page in pages if page.strip())
    if not text:
        raise PdfImportError("PDF sem texto selecionavel. Digitalizacoes precisam de OCR.")
    if len(text) > MAX_REFERENCE_CHARS:
        raise PdfImportError("Texto extraido excede 50 mil caracteres. Use um trecho menor.")

    candidates = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        sentence = sentence.strip()
        if 1 <= len(sentence) <= 500 and terms(sentence) and sentence not in candidates:
            candidates.append(sentence)
    # Spread a small review set across the document; never invent new claims.
    points = (
        [candidates[round(i * (len(candidates) - 1) / 7)] for i in range(8)]
        if len(candidates) > 8
        else candidates
    )
    return {"text": text, "points": points, "page_count": len(reader.pages)}
