from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Mode = Literal["auto", "vector", "graph", "hybrid"]


class EntityInput(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    type: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=20)


class RelationshipInput(BaseModel):
    source: str
    target: str
    type: str
    evidence: str = Field(min_length=1, max_length=8000)
    confidence: float = Field(default=1, ge=0, le=1)


class Extraction(BaseModel):
    entities: list[EntityInput] = Field(default_factory=list, max_length=150)
    relationships: list[RelationshipInput] = Field(default_factory=list, max_length=250)

    @model_validator(mode="after")
    def references(self):
        ids = [e.id for e in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate extraction entity IDs")
        for r in self.relationships:
            if r.source not in ids or r.target not in ids or r.source == r.target:
                raise ValueError("Relationship endpoints must reference distinct extracted entities")
        return self


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=4000)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        if len(value.strip()) < 3:
            raise ValueError("Question must contain at least three non-whitespace characters")
        return value.strip()

    mode: Mode | None = None
    top_k: int | None = Field(None, ge=1, le=30)
    max_depth: int | None = Field(None, ge=1, le=5)


class Evidence(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    page: int | None = None
    score: float = 0
    sources: list[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    aliases: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    evidence: str
    chunk_id: str
    document_id: str
    confidence: float


class GraphPath(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    score: float = 0


class QueryResponse(BaseModel):
    id: str
    question: str
    answer: str
    requested_mode: Mode
    strategy: str
    routing_reason: str
    fallback: str | None = None
    evidence: list[Evidence]
    citations: list[Evidence]
    paths: list[GraphPath]
    latency_ms: float
    retrieval_ms: float
    token_usage: dict[str, int] | None = None
    estimated_cost_usd: float | None = None
    provider: str
    model: str
    warnings: list[str] = Field(default_factory=list)


class TraverseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_ids: list[str] = Field(min_length=1, max_length=10)
    max_depth: int = Field(3, ge=1, le=5)
    limit: int = Field(40, ge=1, le=100)


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    llm_provider: Literal["ollama"] | None = None
    llm_model: str | None = Field(None, min_length=1, max_length=150)
    extraction_model: str | None = Field(None, min_length=1, max_length=150)
    ollama_context_length: int | None = Field(None, ge=2048, le=65536)
    request_timeout: float | None = Field(None, ge=5, le=1800)
    top_k: int | None = Field(None, ge=1, le=30)
    max_depth: int | None = Field(None, ge=1, le=5)
    similarity_threshold: float | None = Field(None, ge=-1, le=1)
    chunk_size: int | None = Field(None, ge=100, le=8000)
    chunk_overlap: int | None = Field(None, ge=0, le=2000)
    context_tokens: int | None = Field(None, ge=256, le=32000)
    reranking: bool | None = None
    fusion: Literal["rrf", "weighted"] | None = None
    vector_weight: float | None = Field(None, ge=0, le=1)
    default_mode: Mode | None = None


class DocumentResponse(BaseModel):
    processing_metadata: dict = Field(default_factory=dict)
    id: str
    name: str
    sha256: str
    size: int
    mime: str
    status: str
    progress: int
    chunks: int
    error: str | None
    created_at: str
    updated_at: str


class GraphStats(BaseModel):
    documents: int
    chunks: int
    entities: int
    relationships: int


class EntityPage(BaseModel):
    items: list[GraphNode]
    offset: int
    limit: int


class PathsResponse(BaseModel):
    paths: list[GraphPath]


class SubgraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    bounded: bool = True


class OverviewResponse(GraphStats):
    queries: int
    recent_queries: list[QueryResponse]
    ingestion: dict[str, int]
    recent_documents: list[DocumentResponse]
    retrieval: list[dict]
    metrics_window: int
