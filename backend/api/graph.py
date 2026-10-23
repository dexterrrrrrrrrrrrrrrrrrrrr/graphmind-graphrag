from fastapi import APIRouter, HTTPException, Request

from backend.api.dependencies import ctx, require_graph
from backend.models.schemas import (
    EntityPage,
    GraphNode,
    GraphStats,
    PathsResponse,
    SubgraphResponse,
    TraverseRequest,
)

router = APIRouter()


@router.get("/api/graph/stats", response_model=GraphStats)
def graph_stats(request: Request) -> dict:
    require_graph(ctx(request))
    return ctx(request).graph.stats()


@router.get("/api/graph/entities", response_model=EntityPage)
def entities(
    request: Request,
    search: str = "",
    type: str | None = None,
    document_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    c = ctx(request)
    require_graph(c)
    rows = c.graph.entities(search[:300], type, document_id, min(max(limit, 1), 200), max(offset, 0))
    return {"items": [r["entity"] for r in rows], "offset": max(offset, 0), "limit": min(max(limit, 1), 200)}


@router.get("/api/graph/entities/{id}", response_model=GraphNode)
def entity(id: str, request: Request) -> dict:
    c = ctx(request)
    require_graph(c)
    result = c.graph.entity(id)
    if not result:
        raise HTTPException(404, "Entity not found")
    return result


@router.get("/api/graph/neighbors/{id}", response_model=PathsResponse)
def neighbors(id: str, request: Request) -> dict:
    c = ctx(request)
    require_graph(c)
    paths = c.graph.traverse([id], 1, c.settings.path_limit)
    return {"paths": [p.model_dump() for p in paths]}


@router.post("/api/graph/traverse", response_model=PathsResponse)
def traverse(body: TraverseRequest, request: Request) -> dict:
    c = ctx(request)
    require_graph(c)
    return {"paths": [p.model_dump() for p in c.graph.traverse(body.entity_ids, body.max_depth, body.limit)]}


@router.get("/api/graph/subgraph", response_model=SubgraphResponse)
def subgraph(
    request: Request,
    document_id: str | None = None,
    search: str = "",
    type: str | None = None,
    offset: int = 0,
    limit: int = 60,
) -> dict:
    c = ctx(request)
    require_graph(c)
    items = c.graph.entities(search[:300], type, document_id, min(max(limit, 1), 100), max(offset, 0))
    nodes = {r["entity"]["id"]: r["entity"] for r in items}
    if not nodes:
        return {"nodes": [], "edges": [], "bounded": True}
    rows = c.graph.read(
        """MATCH (a:Entity)-[r:FACT]->(b:Entity)
        WHERE a.id IN $ids AND b.id IN $ids AND ($doc IS NULL OR r.document_id=$doc)
        RETURN a.id AS source,b.id AS target,r{.*} AS edge ORDER BY r.id LIMIT 300""",
        ids=list(nodes),
        doc=document_id,
    )
    return {
        "nodes": list(nodes.values()),
        "edges": [{**r["edge"], "source": r["source"], "target": r["target"]} for r in rows],
        "bounded": True,
    }
