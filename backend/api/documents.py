import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from backend.api.dependencies import ctx, require_graph
from backend.ingestion.parsing import validate_file
from backend.models.schemas import (
    DocumentResponse,
)

router = APIRouter()


@router.post("/api/documents/upload", response_model=DocumentResponse, status_code=202)
async def upload(request: Request, file: UploadFile = File(...)):
    c = ctx(request)
    require_graph(c)
    settings = c.snapshot()
    try:
        data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    finally:
        await file.close()
    name = Path((file.filename or "").replace("\\", "/")).name
    try:
        validate_file(name, file.content_type or "", data, settings.max_upload_mb * 1024 * 1024)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    digest = hashlib.sha256(data).hexdigest()
    with c.lock:
        duplicate = c.store.duplicate(digest)
        if duplicate:
            return JSONResponse(
                {
                    "error": {
                        "code": "duplicate",
                        "message": "Document already uploaded",
                        "document_id": duplicate["id"],
                    }
                },
                status_code=409,
            )
        id = str(uuid4())
        directory = c.store.directory / "uploads"
        directory.mkdir(exist_ok=True)
        path = directory / id
        path.write_bytes(data)
        path.chmod(0o600)
        try:
            document = c.store.create_document(id, name, digest, len(data), file.content_type)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        c.executor.submit(c.ingestor.run, id, settings)
    return document


@router.get("/api/documents", response_model=list[DocumentResponse])
def documents(request: Request):
    return ctx(request).store.documents()


@router.get("/api/documents/{id}", response_model=DocumentResponse)
@router.get("/api/documents/{id}/status", response_model=DocumentResponse)
def document(id: str, request: Request):
    result = ctx(request).store.document(id)
    if not result:
        raise HTTPException(404, "Document not found")
    return result


@router.get("/api/documents/{id}/source")
def document_source(id: str, request: Request):
    from fastapi.responses import FileResponse

    doc = document(id, request)
    path = ctx(request).store.directory / "uploads" / doc["id"]
    if not path.exists():
        raise HTTPException(404, "Source file not found")
    # Always download untrusted content; never render Markdown/HTML as executable markup.
    return FileResponse(path, media_type="application/octet-stream", filename=doc["name"])


@router.delete("/api/documents/{id}", status_code=204)
def delete_document(id: str, request: Request):
    c = ctx(request)
    require_graph(c)
    with c.lock:
        doc = document(id, request)
        if doc["status"] not in ("ready", "failed"):
            raise HTTPException(409, "Wait for processing to finish before deleting")
        c.graph.delete(id)
        c.store.purge_evidence(id)
        c.store.remove_document(id)
        (c.store.directory / "uploads" / id).unlink(missing_ok=True)
    return Response(status_code=204)


@router.post("/api/documents/{id}/reprocess", response_model=DocumentResponse, status_code=202)
def reprocess(id: str, request: Request):
    c = ctx(request)
    require_graph(c)
    with c.lock:
        doc = document(id, request)
        if doc["status"] not in ("ready", "failed"):
            raise HTTPException(409, "Document is already processing")
        from backend.reasoning.providers import Provider

        state = Provider(c.snapshot()).status()
        if not state["ready"]:
            raise HTTPException(503, state["message"])
        c.store.update_document(id, "queued", 0)
        c.executor.submit(c.ingestor.run, id, c.snapshot())
        return c.store.document(id)
