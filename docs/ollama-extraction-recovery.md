# Recovering partial Ollama relationship extraction

## Observed failure and root cause

The macOS acceptance run reported `Relationship endpoints must reference distinct extracted entities` for `03-partnership.txt`, after the first two documents succeeded. The old extraction flow was:

`chunk → Ollama schema response → Extraction.model_validate_json → cross-reference validator → source/normalization checks → cache → Neo4j → ready`.

The cross-reference validator checked the entire list. One self-reference (`source == target`) **or** reference missing from `entities` raised the same error and rejected all valid siblings. This happened before normalization and Neo4j persistence. The existing prompt did not explicitly forbid self-references or explain exact ID membership. JSON-schema field validation cannot express membership in a dynamically generated entity list.

The failure message alone does not establish which IDs Qwen returned, why it chose them, or whether there was a self-reference versus a missing reference. The actual raw Mac response is unavailable in Codex Cloud. This is an invalid generated-reference failure, not evidence of Neo4j corruption or an out-of-memory failure. No additional model download or memory configuration change is needed to implement the fix. Semantic model behavior on the 8 GB Mac still requires a rerun.

## Fix and invariants

The Ollama wire response now uses `ExtractionResponse`. Ollama receives a full relationship JSON item schema; the application parses each candidate separately with `RelationshipInput`, then applies the same strict graph/source validation. `Extraction` still rejects duplicate entity IDs, unknown endpoints and equal local IDs. Invalid entity identity or malformed overall JSON still fails the response; the application never guesses an identity.

Each individual relationship is discarded if it has an invalid shape/confidence, missing reference, equal endpoint IDs, equal normalized entity identity, unsupported type, non-verbatim evidence or evidence missing either endpoint. Valid entities and relationships are retained. No endpoint is repaired, no direction is reversed and no missing relationship is invented. Citation verification is unchanged. The prompt explicitly requires distinct entities/IDs, exact references, source-grounded evidence, correct actor/object direction and omission instead of guesses.

Rejection counts are logged; safe reason codes and candidate indices are recorded in metadata, without raw model output. Document GET/status responses include `processing_metadata.extraction_diagnostics` with prompt version, total rejected relationship count and at most 50 details (chunk ID, candidate index, reason). The Documents page displays a partial-extraction warning. Diagnostics survive cached extraction reuse. The extraction cache key's prompt version changes to `ollama-v3-partial-relationships`, so an explicit reprocess uses the new prompt; no existing source, cache, graph or volume is automatically deleted.

A document with usable entities/chunks but no valid relationships can finish indexing and become ready, with warnings. Ready means persistence/indexing completed, **not that a complete multi-hop graph was extracted**. If the only partnership candidate was invalid, there is deliberately no replacement partnership edge. Three-hop acceptance must continue to fail until a genuine source-backed partnership is produced. Existing acceptance assertions were not weakened.

## Validation in Codex Cloud

- New partial-extraction suite: **16 tests passed**. Covers self-reference, missing/name-as-ID references, mixed valid/invalid output, malformed individual objects, invalid confidence, unsupported type, invalid evidence, empty relationships, valid partnership direction, canonical self-edge, duplicate IDs, partial/zero-edge ingestion and cached warning persistence.
- Full non-live suite: **84 backend tests passed**, **5 frontend tests passed**, Ruff lint/format and TypeScript/Vite production build passed.
- Isolated Neo4j suite: **9 tests passed** on a fresh dedicated database (Bolt 8067). The new persistence test uses actual Neo4j with mocked Ollama HTTP and test embeddings, verifies a mixed response retains the partnership and full three-hop path, and verifies no self-edge is written. It does not use the Mac database. The first attempt had nine setup errors because the older test container on port 7967 was stopped; those errors are not reported as passes. No existing container volume was reset.
- **Real Qwen3:4b inference: NOT RUN.** Cloud Ollama reports `models=[]`; localhost:8011 is unavailable in this executor and does not refer to the user's Mac. No real-model success is claimed.

Commands executed: `bash scripts/check.sh`; `.venv/bin/pytest -q backend/tests/test_partial_extraction.py backend/tests/test_extraction.py backend/tests/test_answers.py backend/tests/test_audit_regressions.py` (35 passed); `.venv/bin/pytest -q -m integration -k 'not live_sentence'` with the fresh isolated test environment (9 passed); final Ruff and `git diff --check`.

Files changed for this fix: `backend/models/schemas.py`, `backend/knowledge_graph/extraction.py`, `backend/ingestion/service.py`, `backend/core/store.py`, `backend/tests/test_partial_extraction.py`, `backend/tests/test_integration.py`, `backend/tests/fixture_provider.py`, `frontend/src/types/index.ts`, `frontend/src/pages/Documents.tsx`, and this document. The preceding audit changes are included alongside the extraction-recovery fix. `docs/architecture.md`, `docs/validation.md` and README also describe the current behavior and pending live acceptance.

## Rerun on the Mac without resetting data

Rebuild only the isolated acceptance backend from the updated checkout, preserving its existing bind mounts and Neo4j volumes:

```bash
docker compose -p graphmind-acceptance -f docker-compose.yml -f docker-compose.acceptance.yml up -d --build --no-deps backend
```

Find the failed document via `GET http://localhost:8011/api/documents`. Reprocess **only its ID** (replace the example value):

```bash
curl -fsS -X POST http://localhost:8011/api/documents/FAILED_DOCUMENT_ID/reprocess
curl -fsS http://localhost:8011/api/documents/FAILED_DOCUMENT_ID/status
```

Wait until ready or failed, inspect `processing_metadata.extraction_diagnostics`, and inspect actual relationship evidence in the graph explorer. Do not infer extraction quality merely from a ready status. The two successful documents do not need reprocessing. Then run the existing acceptance script:

```bash
.venv/bin/python scripts/demo.py --api http://localhost:8011/api --output .data/local-acceptance-report
```

It must still verify MedCore, all three source citations and the actual three-hop path. If the relationship list is empty after filtering, inspect warnings and rerun the model deliberately; do not manually fabricate an edge to make acceptance pass. Do not use `down -v`, delete documents, or reset the database.
