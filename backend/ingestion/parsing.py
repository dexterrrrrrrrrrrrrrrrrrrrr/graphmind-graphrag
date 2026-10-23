import hashlib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf

MIMES = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain", "text/x-markdown"},
}


@dataclass
class Page:
    text: str
    number: int | None


def validate_file(name: str, mime: str, data: bytes, max_bytes: int):
    if not name or len(name) > 240 or any(ord(c) < 32 for c in name):
        raise ValueError("Invalid document filename")
    extension = Path(name).suffix.lower()
    if extension not in MIMES or mime.split(";")[0] not in MIMES[extension]:
        raise ValueError("Supported files: PDF, TXT, Markdown with matching MIME type")
    if not data or len(data) > max_bytes:
        raise ValueError("File is empty or exceeds upload size limit")
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF signature")
    if extension != ".pdf" and b"\x00" in data:
        raise ValueError("Binary data is not a text document")


def parse(data: bytes, extension: str) -> list[Page]:
    if extension == ".pdf":
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if document.needs_pass:
                raise ValueError("Encrypted PDFs are not supported")
            if len(document) > 1000:
                raise ValueError("PDF page limit (1000) exceeded")
            pages = [Page(page.get_text(), i + 1) for i, page in enumerate(document)]
    else:
        text = data.decode("utf-8-sig")
        if extension == ".md":
            from markdown_it import MarkdownIt

            parts = []
            for token in MarkdownIt().parse(text):
                if token.type == "inline":
                    parts.append(
                        "".join(
                            child.content
                            if child.type in ("text", "code_inline", "image")
                            else "\n"
                            if child.type in ("softbreak", "hardbreak")
                            else ""
                            for child in token.children or []
                        )
                    )
                elif token.type in ("fence", "code_block"):
                    parts.append(token.content)
            text = "\n".join(parts)
        pages = [Page(text, None)]
    if not any(p.text.strip() for p in pages):
        raise ValueError("No readable text; scanned PDFs require OCR before uploading")
    return pages


def chunk_pages(pages: list[Page], document_id: str, size: int, overlap: int) -> list[dict]:
    if not 0 <= overlap < size:
        raise ValueError("Overlap must be smaller than chunk size")
    result = []
    for page in pages:
        text = unicodedata.normalize("NFC", page.text).strip()
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                split = text.rfind(" ", start + size // 2, end)
                if split > start:
                    end = split
            content = text[start:end].strip()
            if content:
                index = len(result)
                id = hashlib.sha256(f"{document_id}:{index}:{content}".encode()).hexdigest()
                result.append(
                    {
                        "id": id,
                        "document_id": document_id,
                        "text": content,
                        "page": page.number,
                        "position": index,
                    }
                )
            if end == len(text):
                break
            start = max(start + 1, end - overlap)
    if len(result) > 3000:
        raise ValueError("Document chunk limit (3000) exceeded")
    return result
