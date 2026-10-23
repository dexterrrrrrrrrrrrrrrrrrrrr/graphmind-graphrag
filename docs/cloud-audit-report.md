# GraphMind cloud engineering audit

Date: 2026-10-23 UTC. Baseline commit: `b7052a5f8eb7e087500169f114ce0ef35736eab5`.

**Overall assessment: PARTIAL.** Available deterministic checks, isolated database integration, browser workflow, builds, compatibility and scoped security scans pass after targeted fixes. **Real Ollama extraction, answer quality, live GraphRAG acceptance and real-model benchmarks are NOT RUN:** the reachable cloud Ollama service reports an empty installed-model list. No weights were downloaded, and no paid inference was used. Changes remain uncommitted and unpushed.

## Scope and architecture assessment

Reviewed README, architecture, API, validation, evaluation and macOS acceptance documentation; ingestion/parser/chunker, embedding service, extraction schemas/validation/cache, graph repository, retrieval/router/fusion, answer/provider services, SQLite control store, API/middleware, evaluation/analytics, all seven frontend pages, shared API/SSE client, graph/citation components, Docker configuration and CI.

The modular boundaries are suitable for a local research application. Immutable source files and SQLite job/configuration records complement Neo4j evidence, entities, relationship provenance and native vectors. Ingestion validates source-supported structured extraction before document replacement; ready status follows graph/index readiness. Retrieval modes remain distinct, with no silent benchmark fallback. The installed Neo4j GraphRAG index helper is exercised by integration tests rather than assumed from an outdated interface.

The application is **not yet validated as a reliable autonomous semantic reasoner or an Internet-facing multi-user service**. Exact quotes establish attribution, not entailment. Bounded graph retrieval and lexical routing/reranking are transparent heuristics. Cross-store atomicity and durable scheduling remain limitations.

## Commands and fresh results

Commands ran from the repository unless stated otherwise. Docker commands used the managed local socket with inherited remote endpoint/TLS selectors cleared; credentials and resolved Compose secrets were not printed. Test services never targeted the main application database.

| Check / command | Result | Scope |
|---|---|---|
| `bash scripts/check.sh` | PASS | Ruff lint/format; **68 backend unit/API/protocol tests**; **5 Vitest tests**; TypeScript and production Vite build |
| `.venv/bin/pytest -q -m integration -k 'not live_sentence'` with dedicated test environment | PASS: **8 tests**, 70 deselected | Real fresh Neo4j 5.26.32; deterministic test embeddings and explicit extraction/answer doubles |
| `CHROMIUM_PATH=/usr/bin/chromium npx playwright test` in `frontend` | PASS: **1 workflow**, 9.1 s runner time | All seven pages, upload/progress, three-hop fixture answer/citations, actual graph provenance, graph filter regression, comparison, benchmark, analytics, settings, mobile width; no live LLM |
| `UV_CACHE_DIR=/workspace/.cache/uv uv pip check` | PASS | 73 installed Python distributions compatible |
| `UV_CACHE_DIR=/workspace/.cache/uv uv build --out-dir .data/cloud-audit-package` | PASS | Source distribution and wheel build |
| `docker compose config --quiet` and base + `docker-compose.cloud.yml` / `docker-compose.acceptance.yml` variants | PASS: all three | Configuration parsing; no image rebuild or destructive volume operations |
| Read-only main Neo4j connectivity/index/count checks | PASS | Native vector index ONLINE; 3 documents, 3 chunks, 4 entities, 3 relationships |
| Read-only baseline comparison + SQLite integrity | PASS | Original 3 documents, recorded fields/provenance, source SHA-256 hashes, graph counts, and 1 evaluation ID retained; SQLite `integrity_check=ok` |
| Cached `Embedder.embed()` with `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` | PASS | Actual CPU all-MiniLM-L6-v2, two 384-dimensional finite vectors; load + encode measured 5.403 s in this executor, not a retrieval/LLM benchmark |
| Gitleaks 8.24.3 `git --log-opts='--all'` and `dir` on safe source candidates | PASS: zero findings | Four commits; tracked + nonignored untracked source; release archive checksum verified |
| `npm --prefix frontend audit --json` | PASS: zero reported vulnerabilities | Full frontend lockfile graph |
| `uvx pip-audit --path .venv/lib/python3.12/site-packages --skip-editable --format json` | No known vulnerabilities in assessed packages | Editable project skipped; `torch 2.14.1+cpu` could not be matched in PyPI advisories and is **not covered** |
| `curl http://localhost:11434/api/tags` | Connected; `models=[]` | Missing Qwen weights, not an inference pass |
| Existing `/api/health` | DEGRADED / 503 | Old running backend image retained startup failure flag; selected Ollama model missing. Source readiness fix is tested, but images were not rebuilt/redeployed |
| Two opt-in live-model backend checks | **NOT RUN** | Real provider smoke and real Sentence Transformers + Ollama three-document GraphRAG acceptance require installed weights |
| Real vector vs hybrid benchmark accuracy/latency/tokens | **NOT RUN** | Fixture benchmark execution verifies metrics plumbing only; no semantic performance claim |

Initial baseline checks passed 52 backend tests and 3 frontend tests before changes. The first database run failed with 7 setup errors against the restored pre-existing fixture instance. Its debug log reports `org.apache.lucene.store.AlreadyClosedException: Underlying file changed by an external force` for the vector index `write.lock`, followed by `TransactionCommitFailed` / `TransactionStartFailed`. This was an observed cloud recovery/storage issue, not relabeled as a pass. A fresh **separate** `graphmind-cloud-audit-neo4j` instance/volume on Bolt 7967 passed the initial seven checks and then the added real-cycle regression (eight total). The damaged prior test instance and all development volumes were retained.

Two auxiliary diagnostic commands initially failed: `uv pip check` used a read-only home cache (rerun successfully with workspace cache), and direct host hashing could not read root-owned upload files (rerun read-only inside the existing backend container). A baseline comparison initially compared full rows against a manifest containing only selected fields; the corrected comparison checked every recorded field. These did not require permission changes or source-data changes.

## Bugs found, minimal fixes and regressions

| Finding / root cause | Implemented fix | Regression coverage |
|---|---|---|
| Citation validator reduced valid quotes to a set of chunk IDs; a fabricated second quote for the same chunk could pass | Require every quote to match its actual cited chunk, equal citation/quote ID sets, and nonblank claim text; invalid claims still fail closed | Mixed valid/fabricated quotes for one ID and whitespace-only claim rejected |
| Benchmark citation precision checked excerpt text but ignored source document identity | Require expected document ID as well as expected verbatim text | Correct text from wrong document receives zero citation correctness/recall |
| Ingestion queried Neo4j before its exception handler, leaving a queued job stuck if connectivity failed | Include existence check in failure boundary; distinguish unknown graph state from confirmed absence so cleanup cannot delete unknown prior evidence | Connection failure records failed job, performs no graph deletion |
| Failed schema startup was attempted once, permanently disabling graph API readiness after a service startup race | Retry failed initialization on health/graph API checks, single initialization lock, 15-second cooldown; never resubmit document jobs during recovery | Failure, cooldown, recovery, cleared error and no job mutations |
| Settings snapshot acquired the operation lock held throughout inference, blocking health/Ollama status polling | Copy the settings model without the operation lock; settings writes already atomically replace the model | Snapshot from another thread completes while the operation lock is held |
| Blank extraction names/types/aliases and substring-only entity names could pass source validation; two local IDs could normalize to one self-edge | Reject blank values, require word-boundary source mentions, reject relationships collapsing to the same normalized entity | Four blank/partial-name cases and canonical self-edge rejection |
| Ollama stream events assumed dictionary/string shapes; absent usage was reported as measured zero | Reject malformed event/content shapes with safe provider errors; stop at terminal event; absent/negative/noninteger usage remains unavailable | Three malformed protocol cases and three missing/invalid usage cases; existing measured-usage and retry tests preserved |
| Graph explorer always preferred navigation-state paths, so filters appeared to do nothing after following an answer path | Explicit return-to-full-graph control; filters exit path mode; disable irrelevant path-mode pagination | Browser searches Rahul after opening highlighted paths and sees one node, zero edges |
| Frontend SSE parser had no direct regression coverage | Added fragmented-event and interrupted-stream tests without changing working parsing behavior | Progress is separate from final answer; interrupted stream rejects |
| API/evaluation docs still described removed providers, offline production generation, paid token pricing and no streaming | Corrected current endpoint/model/streaming/cost/reprocessing contracts | Reviewed against routes/provider implementation; actual tests/build remain passing |

Added **20 backend regression cases** (16 unit/protocol cases, 3 parametrized graph-hop cases and a source-backed cycle case), **2 frontend unit tests**, and extended the existing browser workflow. Production code contains no fixture answer or hardcoded benchmark success.

## Pipeline and multi-hop findings

- Uploads enforce extension/MIME, byte limits, PDF signatures, safe UUID storage and duplicate SHA-256. Parsing preserves PDF pages, rejects encrypted/unreadable PDFs, and supports UTF-8 TXT/Markdown. Chunk identity and overlap are deterministic. Explicit page/chunk limits bound normal workloads.
- Embedding inference is CPU-local with finite-vector/dimension checks, a cached model, batch size 32 and bounded Torch threads. Test-only hashes are confined to isolated fixture code/database model identity.
- Extraction uses the installed Ollama JSON-schema API contract with Pydantic, validates endpoints/types and exact evidence, normalizes exact type/name identities and explicit aliases, and caches only validated results. Failure is visible; no repair invents missing facts.
- Relationship IDs include source, type, target and chunk. Persisted `FACT` edges retain original direction, semantic type, confidence and actual document/chunk/excerpt provenance. Queries use parameters; executable labels are constants, never model/user-controlled Cypher.
- New real-database tests explicitly validate depth 1/2/3, ordered chain nodes, edge source/target, corresponding source documents/chunks, exact excerpts, relationship allowlisting and document filtering. An additional source-backed cyclic relationship verifies actual cycle avoidance and path deduplication. Existing tests exercise bounded results, deletion and missing-entity refusal.
- Retrieval intentionally follows incoming **and** outgoing adjacency for questions such as “Who founded AlphaTech?”. Stored source/target direction is preserved and tested in reverse traversal. Bidirectional connectivity is not equivalent to a directed causal proof; generation is instructed to preserve semantics. No LLM creates graph paths.
- Vector mode never traverses; graph mode never embeds a query. Hybrid fuses by chunk ID, reranks and conservatively budgets whole sources/paths. Displayed paths require all support chunks to remain in supplied context. Missing entities do not silently trigger a different baseline mode.
- All generated claims must cite retrieved chunk IDs and exact source quotes. Empty evidence skips the LLM and returns the fixed refusal. Invalid claims are removed. React renders source text as escaped text; source files download as attachments.

## Security assessment

No detected credential exposure in scanned source or history. `.gitignore` excludes environment secrets, local databases/uploads/cache, models/weights, runtime keys, logs and build artifacts while retaining `backend/models` source. Source checks do not modify `.env` or reveal database passwords. No commit or push was performed.

Controls reviewed: local Ollama endpoint restrictions, cloud-model exclusion, no redirects/proxying of local inference, no paid provider fallback, upload/body limits, parameterized Cypher, bounded traversal, validated settings allowlist, safe API errors, per-client request limits, download-only source delivery, frontend escaping and Nginx CSP. Prompt policy treats retrieved documents as untrusted instructions. These reduce risk; neither a prompt nor quotation checks prove resistance to adversarial semantic content.

Remaining security/deployment limits:

- No application authentication/authorization or tenant isolation. Keep loopback bindings; use an authenticated gateway before network deployment. CORS is not access control. Native Ollama host binding on macOS requires firewall restrictions.
- User-supplied PDFs are parsed in-process. Page/file limits do not provide a CPU/memory sandbox or protect against every decompression/parser attack. Consider an isolated parsing worker with resource limits for untrusted public uploads.
- Gitleaks is pattern based, not proof that all sensitive data is absent. Dependency advisories are point-in-time; Torch CPU and container OS/image vulnerabilities were not assessed by the package scans. No container vulnerability scanner was run.
- Exact source presence cannot reject every negated/hypothetical relationship or a claim that does not logically follow from its quote. Add adversarial and semantic entailment evaluation before trusting high-stakes answers.

## Performance and reliability assessment

No live LLM latency, throughput, memory benchmark or hybrid quality gain is claimed. Reported test durations describe this cloud test run only.

Existing safeguards are appropriate for a single local workspace: one ingestion worker, serialized inference, default unload-after-call, CPU embedding batch size 32, local extraction cache, native Neo4j cosine index, bounded top-K/depth/frontier/adjacency, RRF deduplication and optional cheap lexical reranking. Query/provider token counts now remain unavailable instead of fabricated when Ollama omits valid usage. Lock-free settings snapshots remove a demonstrated avoidable dependency of health polling on inference duration.

Remaining issues / recommended next work:

1. **Semantic acceptance:** execute real Qwen extraction/answers and held-out multi-hop/adversarial questions locally. Grounding is attribution validation, not truth/entailment verification.
2. **Concurrency/backpressure:** operation/inference locks serialize long calls; SSE creates per-request worker threads and disconnected requests can continue inference. There is no bounded global admission queue/cancellation contract. The API is not load-tested; add admission limits and disconnect-aware cancellation before concurrent deployment.
3. **Timeout semantics:** HTTPX inactivity timeouts, per-stream elapsed checks and up to three retry attempts are not a strict whole-request deadline including lock wait/backoff. Bound total operation duration and record queue/retry time if enforcing service SLAs.
4. **Cross-store recovery:** SQLite and Neo4j cannot commit atomically. A crash after graph replacement but before SQLite readiness can leave an interrupted control record with graph evidence; failed reprocessing can retain prior evidence while the current job is failed. Add explicit reconciliation/attempt versions before durable production scheduling.
5. **Cache reproducibility:** extraction cache keys use a model tag, not immutable Ollama digest, and do not include every generation option. Changing weights under a tag requires manual invalidation. Store model digest and full extraction configuration for research reproducibility.
6. **Graph scale:** exact query linking scans candidate names/aliases; per-frontier expansion performs multiple queries; alias cleanup recomputes surviving aliases globally. Traversal is bounded but can omit relevant high-degree paths and ranking favors longer paths. Profile realistic datasets before changing indexes/queries.
7. **Ranking/context:** lexical reranking is not a learned relevance model; graph/vector weighted scores have different scales. UTF-8 byte budgeting is conservative, not a model tokenizer; source-only selection can exhaust room for complete paths. Context/output settings are not a calibrated model-specific token budget.
8. **Evaluation validity:** expected document IDs are now enforced, but dataset resolution still uses unique filenames rather than corpus hashes. Normalized answer containment can score negated/wrong-context answers as correct. Aggregates mix retained runs/settings. Use corpus digests, independent entailment labels and matched, randomized larger experiments.
9. **Runtime deployment:** running containers still use pre-audit images. Rebuild during planned local acceptance to activate fixes; do not confuse the reachable old dashboard with a deployment validation of these source changes.

## MacBook-required acceptance and final disposition

Follow [macOS local acceptance](macos-local-acceptance.md) using native Ollama and the isolated acceptance Compose project. Install `qwen3:4b` once, confirm `/api/tags`, run `python -m scripts.check_local_model`, build/start GraphMind, then `scripts/demo.py --api http://localhost:8011/api --output .data/local-acceptance-report`. Run the documented one-/two-/three-hop assertions; inspect actual extracted directed facts, source quotations/citations, refusal behavior, comparison and JSON/CSV results. Measure Apple Silicon memory/latency and restart persistence on that isolated stack. Preserve main data and never run `down -v` against it.

**PASS:** scoped automated engineering checks and corrected deterministic GraphRAG plumbing. **NOT RUN:** genuine Qwen inference/semantic acceptance, live-model benchmark, Apple Silicon performance, adversarial/load/container-image security testing. **Overall PARTIAL** until those checks are executed and documented. No publication was attempted or authorized for this audit.
