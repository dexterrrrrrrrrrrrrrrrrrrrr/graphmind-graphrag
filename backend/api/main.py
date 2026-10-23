import asyncio
import logging
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import analytics, documents, evaluation, graph, ollama, queries, settings
from backend.api.dependencies import ctx
from backend.core.config import get_settings
from backend.core.context import Context
from backend.core.limits import BodyLimitMiddleware, RequestTooLarge
from backend.core.logging import configure_logging
from backend.reasoning.providers import Provider, ProviderError

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    context = Context(get_settings())
    app.state.context = context
    await asyncio.to_thread(context.initialize)
    # Warmup is read-only, local-model download; no LLM calls are made at startup.
    warmup = asyncio.create_task(asyncio.to_thread(context.warm_embeddings))
    yield
    await warmup
    await asyncio.to_thread(context.close)


app = FastAPI(
    title="GraphMind API",
    version="0.1.0",
    lifespan=lifespan,
    description="Evidence-grounded hybrid GraphRAG. Local-only development API; no built-in user auth.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

app.add_middleware(BodyLimitMiddleware, max_upload_bytes=get_settings().max_upload_mb * 1024 * 1024)
rate_windows = defaultdict(deque)


@app.middleware("http")
async def request_limits(request: Request, call_next):
    key = request.client.host if request.client else "unknown"
    window = rate_windows[key]
    now = monotonic()
    while window and window[0] < now - 60:
        window.popleft()
    limit = (
        ctx(request).settings.requests_per_minute
        if hasattr(request.app.state, "context")
        else get_settings().requests_per_minute
    )
    if len(window) >= limit:
        return JSONResponse(
            {"error": {"code": "rate_limited", "message": "Request limit exceeded"}},
            status_code=429,
            headers={"Retry-After": "60"},
        )
    window.append(now)
    # Bound memory for inactive clients as well as requests per client.
    if len(rate_windows) > 10000:
        for ip in list(rate_windows):
            if not rate_windows[ip] or rate_windows[ip][-1] < now - 60:
                del rate_windows[ip]
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_error(request, error):
    return JSONResponse(
        {"error": {"code": str(error.status_code), "message": error.detail}},
        status_code=error.status_code,
        headers=error.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    return JSONResponse(
        {
            "error": {
                "code": "validation",
                "message": "Invalid request",
                "details": [{"loc": list(e["loc"]), "message": e["msg"]} for e in error.errors()],
            }
        },
        status_code=422,
    )


@app.exception_handler(Exception)
async def unexpected_error(request, error):
    log.error("request_failed path=%s error_type=%s", request.url.path, type(error).__name__)
    return JSONResponse(
        {
            "error": {
                "code": "service_error",
                "message": "Operation failed. Check service readiness and provider configuration; no retrieval fallback was used.",
            }
        },
        status_code=503,
    )


@app.get("/api/health")
def health(request: Request) -> dict:
    c = ctx(request)
    graph_ok = False
    try:
        c.graph.driver.verify_connectivity()
        graph_ok = c.graph_ready and c.graph.index_ready()
    except Exception:
        pass
    ollama_state = Provider(c.snapshot()).status()
    ready = graph_ok and c.embedder.ready and ollama_state["ready"]
    result = {
        "status": "ready" if ready else "degraded",
        "service": "graphmind",
        "neo4j": graph_ok,
        "vector_index": graph_ok,
        "embedding_model": c.embedder.ready,
        "embedding_error": c.embedding_error,
        "provider": c.settings.llm_provider,
        "generation": ollama_state,
    }
    return JSONResponse(result, status_code=200 if ready else 503)


@app.get("/api/openapi.json", include_in_schema=False)
def openapi_alias():
    return app.openapi()


@app.get("/api/docs", include_in_schema=False)
def docs_alias():
    from fastapi.openapi.docs import get_swagger_ui_html

    return get_swagger_ui_html(openapi_url="/api/openapi.json", title="GraphMind API")


@app.exception_handler(RequestTooLarge)
async def too_large(request, error):
    return JSONResponse(
        {"error": {"code": "too_large", "message": "Request body exceeds limit"}}, status_code=413
    )


@app.exception_handler(ProviderError)
async def provider_configuration_error(request, error):
    return JSONResponse({"error": {"code": "provider_configuration", "message": str(error)}}, status_code=503)


for routes in (documents, queries, graph, evaluation, analytics, settings, ollama):
    app.include_router(routes.router)
