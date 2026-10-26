"""PDF import is local, authenticated and reviewable before selection."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services.pdf_import import extract_pdf


def pdf_with_text(text: str | None, *, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=400)
    if text is not None:
        font = writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 30 330 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("test-password")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def test_pdf_preview_can_be_saved_and_selected_for_next_session(client):
    body = pdf_with_text("A luz permite fotossintese nas plantas.")
    preview = client.post(
        "/api/v1/contents/import-pdf", files={"file": ("plantas.pdf", body, "application/pdf")}
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["page_count"] == 1
    assert data["points"] == ["A luz permite fotossintese nas plantas."]
    assert client.get("/api/v1/contents").json() == []  # import is only a preview
    saved = client.post(
        "/api/v1/contents",
        json={"title": "Plantas", "text": data["text"], "points": data["points"], "source": "pdf"},
    )
    assert saved.status_code == 201, saved.text
    cid = saved.json()["id"]
    assert saved.json()["source"] == "pdf"
    assert client.put("/api/v1/experience/selection", json={"content_id": cid}).status_code == 200
    assert client.get("/api/v1/experience/selection").json()["selected_content_id"] == cid


def test_pdf_import_rejects_unauthorized_invalid_scanned_encrypted_and_large(client):
    url = "/api/v1/contents/import-pdf"
    valid = pdf_with_text("Texto de exemplo.")
    assert (
        client.post(
            url, headers={"Authorization": ""}, files={"file": ("x.pdf", valid)}
        ).status_code
        == 401
    )
    for name, body, expected in (
        ("x.txt", valid, 422),
        ("x.pdf", b"not a pdf", 422),
        ("x.pdf", pdf_with_text(None), 422),
        ("x.pdf", pdf_with_text("Secreto.", encrypted=True), 422),
        ("x.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024), 413),
    ):
        response = client.post(url, files={"file": (name, body, "application/pdf")})
        assert response.status_code == expected, (name, response.text)
    assert client.get("/api/v1/contents").json() == []


def test_pdf_suggests_few_source_grounded_points_across_document():
    sentences = [f"O processo numero {i} explica agua e plantas." for i in range(12)]
    extracted = extract_pdf(pdf_with_text(" ".join(sentences)))
    assert len(extracted["points"]) == 8
    assert extracted["points"][0] == sentences[0]
    assert extracted["points"][-1] == sentences[-1]
    assert all(point in extracted["text"] for point in extracted["points"])
