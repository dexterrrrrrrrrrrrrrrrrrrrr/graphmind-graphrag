from fastapi import HTTPException, Request

from backend.core.context import Context


def ctx(request: Request) -> Context:
    return request.app.state.context


def require_graph(context: Context) -> None:
    if not context.graph_ready:
        context.ensure_graph()
    if not context.graph_ready:
        raise HTTPException(
            503, "Neo4j is not ready; check credentials, connectivity and schema initialization"
        )
