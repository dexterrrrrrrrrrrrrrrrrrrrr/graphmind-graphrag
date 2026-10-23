from fastapi import APIRouter, Request

from backend.api.dependencies import ctx, require_graph
from backend.models.schemas import (
    QueryRequest,
    QueryResponse,
)

router = APIRouter()


@router.post("/api/query", response_model=QueryResponse)
def query(body: QueryRequest, request: Request):
    c = ctx(request)
    require_graph(c)
    with c.lock:
        return c.query.ask(body, c.snapshot())


@router.get("/api/queries", response_model=list[QueryResponse])
def history(request: Request, limit: int = 50):
    return ctx(request).store.records("queries", min(max(limit, 1), 200))


@router.post("/api/query/compare", response_model=dict[str, QueryResponse])
def compare(body: QueryRequest, request: Request):
    c = ctx(request)
    require_graph(c)
    with c.lock:
        settings = c.snapshot()
        return {
            mode: c.query.ask(body.model_copy(update={"mode": mode}), settings)
            for mode in ("vector", "hybrid")
        }


@router.post("/api/query/stream")
def stream_query(body: QueryRequest, request: Request):
    """SSE inference progress followed by a citation-validated answer. No raw drafts."""
    import json
    from queue import Empty, Full, Queue
    from threading import Event, Thread

    from fastapi.responses import StreamingResponse

    from backend.reasoning.providers import ProviderError

    c = ctx(request)
    require_graph(c)
    snapshot = c.snapshot()
    events = Queue(maxsize=64)
    cancelled = Event()

    def progress(kind, payload):
        if not cancelled.is_set():
            try:
                events.put_nowait((kind, payload))
            except Full:
                pass  # Coalesce progress when a browser reads slowly.

    def finish(kind, payload):
        while not cancelled.is_set():
            try:
                events.put((kind, payload), timeout=1)
                return
            except Full:
                continue

    def work():
        try:
            with c.lock:
                result = c.query.ask(body, snapshot, progress=progress)
            finish("answer", result.model_dump())
        except Exception as error:
            finish(
                "error",
                {
                    "message": str(error)
                    if isinstance(error, ProviderError)
                    else "Local inference failed. Check Ollama, installed models and memory. No fallback was used."
                },
            )

    def iterate():
        worker = Thread(target=work, daemon=True, name="ollama-stream")
        worker.start()
        try:
            while True:
                try:
                    kind, payload = events.get(timeout=1)
                except Empty:
                    yield ": keepalive\n\n"
                    continue
                yield "data: " + json.dumps({"event": kind, "data": payload}) + "\n\n"
                if kind in {"answer", "error"}:
                    break
        finally:
            cancelled.set()

    return StreamingResponse(
        iterate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
