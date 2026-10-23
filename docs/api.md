# API contract

Interactive documentation: backend port 8000, `/api/docs`; machine schema: `/api/openapi.json`. `/docs` and `/openapi.json` are available on the native backend too. Frontend requests use the same-origin `/api` proxy.

Errors have `{"error":{"code":"…","message":"…"}}`; validation errors also provide safe field locations/messages. Missing resources: 404; duplicate/busy/conflicting resources: 409; invalid input: 422; oversized body: 413; rate limit: 429 with `Retry-After`; unavailable dependencies/provider failures: 503. Internal exception details and credentials are not returned.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | /api/health | Live Neo4j/index connectivity plus model readiness; 200 ready or 503 degraded |
| POST | /api/documents/upload | Multipart `file`; 202 queued; duplicate returns existing ID with 409 |
| GET | /api/documents | Documents, progress, errors, provenance/configuration metadata |
| GET | /api/documents/{id} | Document metadata |
| GET | /api/documents/{id}/status | Same metadata for polling |
| GET | /api/documents/{id}/source | Attachment download, never executable inline document rendering |
| DELETE | /api/documents/{id} | Delete source and evidence; 204; rejects active ingestion |
| POST | /api/documents/{id}/reprocess | Queue with current configuration; preserve prior graph until validated replacement |
| POST | /api/query | `{question, mode?, top_k?, max_depth?}`; omitted mode uses saved default |
| POST | /api/query/compare | Vector and hybrid results under one settings snapshot; no silent fallback |
| POST | /api/query/stream | SSE progress followed by one citation-validated answer or an explicit error |
| GET | /api/ollama/status | Local connection, installed/loaded models and selected-model readiness |
| GET | /api/ollama/models | Installed local models; cloud entries excluded |
| GET | /api/queries | Bounded recent query history |
| GET | /api/graph/stats | Graph counts |
| GET | /api/graph/entities | Bounded `search`, `type`, `document_id`, `offset`, `limit` filters |
| GET | /api/graph/entities/{id} | Entity properties |
| GET | /api/graph/neighbors/{id} | Bounded one-hop database paths |
| POST | /api/graph/traverse | `{entity_ids,max_depth,limit}`; bounded simple paths |
| GET | /api/graph/subgraph | Paginated nodes with a bounded set of relationships among those nodes |
| POST | /api/evaluation/run | Execute the versioned dataset; long-running synchronous response |
| GET | /api/evaluation/results | Retained run records |
| GET | /api/evaluation/summary | Applicable metric means and explicit execution/failure counts |
| GET | /api/evaluation/results/{id}/export | JSON or CSV attachment |
| GET | /api/analytics/overview | Live counts, retained query count, recent activity, ingestion states |
| GET | /api/analytics/latency | Mean, P50/P95, samples and available token totals (last 1,000 queries) |
| GET | /api/analytics/retrieval | Mode distribution, evidence counts, empty retrievals and evaluation summaries |
| GET | /api/settings | Nonsecret editable settings, model IDs and upload/retrieval configuration |
| PATCH | /api/settings | Validated allowlisted nonsecret updates; persisted locally |

Query response fields: ID, question, answer, requested mode, selected strategy and routing reason, explicit fallback (`null` when none), retrieved evidence with scores/source kinds, verified source citations, database-derived paths, retrieval/total latency, available token counts, optional estimated cost, provider/model and warnings. Ollama is the sole inference provider; empty evidence returns the insufficient-evidence response without inference. Successful request execution does not guarantee answerable evidence.

Modes are `vector`, `graph`, `hybrid`, `auto`. Graph depth is capped at five. Explicit mode errors propagate; benchmark rows record failures. `/api/query/stream` sends SSE loading/generation progress and only exposes the final answer after schema/citation validation. Ordinary query, comparison and benchmark endpoints return complete JSON. No unverified draft tokens reach the browser.
