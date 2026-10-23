import pymupdf
import pytest

from backend.ingestion.parsing import Page, chunk_pages, parse, validate_file


def test_pdf_pages_and_metadata():
    document = pymupdf.open()
    for text in ["Rahul Sharma founded AlphaTech.", "AlphaTech acquired DataVision."]:
        document.new_page().insert_text((40, 40), text)
    pages = parse(document.tobytes(), ".pdf")
    assert [p.number for p in pages] == [1, 2]
    assert "AlphaTech" in pages[0].text
    assert chunk_pages(pages, "doc", 200, 20)[1]["page"] == 2


@pytest.mark.parametrize("extension", [".txt", ".md"])
def test_utf8_parser(extension):
    assert parse("Résumé ∑".encode(), extension)[0].text == "Résumé ∑"


@pytest.mark.parametrize(
    "name,mime,data",
    [
        ("x.exe", "text/plain", b"hello"),
        ("x.pdf", "text/plain", b"%PDF-"),
        ("x.pdf", "application/pdf", b"not pdf"),
        ("x.txt", "text/plain", b"\x00a"),
        ("x.txt", "text/plain", b""),
    ],
)
def test_invalid_upload(name, mime, data):
    with pytest.raises(ValueError):
        validate_file(name, mime, data, 100)


def test_file_limit_and_malformed_pdf():
    with pytest.raises(ValueError):
        validate_file("x.txt", "text/plain", b"a" * 101, 100)
    with pytest.raises(Exception):
        parse(b"%PDF-broken", ".pdf")
    with pytest.raises(ValueError):
        parse(b"  ", ".txt")


def test_chunks_overlap_no_loss_stable_ids():
    text = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_pages([Page(text, 7)], "doc", 120, 15)
    assert len(chunks) > 5
    assert all(len(c["text"]) <= 120 and c["document_id"] == "doc" and c["page"] == 7 for c in chunks)
    assert all(f"word{i}" in " ".join(c["text"] for c in chunks) for i in range(200))
    assert chunks == chunk_pages([Page(text, 7)], "doc", 120, 15)
    assert len({c["id"] for c in chunks}) == len(chunks)
    with pytest.raises(ValueError):
        chunk_pages([Page(text, 1)], "doc", 100, 100)


def test_markdown_readable_text_preserves_fact_names():
    pages = parse(b"# Acquisition\n\n**AlphaTech** acquired [DataVision](https://example.com).", ".md")
    assert "AlphaTech acquired DataVision." in pages[0].text
    assert "https://" not in pages[0].text
