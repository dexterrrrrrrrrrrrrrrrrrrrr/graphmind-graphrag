> Current extraction-recovery validation: [ollama-extraction-recovery.md](ollama-extraction-recovery.md): 84 backend unit/API/protocol tests, 9 isolated real-Neo4j integration tests with mocked inference, 5 frontend tests, Ruff, TypeScript and production build passed. **Real Qwen3:4b end-to-end verification remains pending.**

> Earlier engineering audit: [cloud-audit-report.md](cloud-audit-report.md). The initial publication results below are historical; the audit records the current rerun and additional regressions. Real Ollama acceptance is still pending.

# Validation status for initial publication

Date: 2026-10-23 (Asia/Kolkata). **Live Ollama/GraphRAG acceptance is pending.** The user authorized initial publication after non-LLM quality/security checks, with this limitation documented. Cloud model downloads are stopped; they are not a publication prerequisite.

## Executed checks

| Check | Outcome | What it establishes |
|---|---|---|
| Backend unit/API/protocol suite | 52 passed | Parsing/chunking, normalization/provenance, vector/fusion/routing logic, citation rejection, settings/defaults, extraction-cache ownership, SSE and Ollama protocol; inference calls mocked |
| Isolated Neo4j integration | 4 passed | Real database persistence, native vector index, directed multi-hop paths, citations, cycle/result limits, deletion/cache/idempotency, reconnect and evaluation plumbing; explicit model doubles and test vectors |
| Frontend unit tests | 3 passed | UI utility behavior |
| Playwright workflow | 1 passed | All seven pages, upload → answer/citations → graph → comparison → benchmark → analytics → settings and mobile layout; real isolated Neo4j, mocked inference/embeddings |
| Python package build | Passed | Source distribution and wheel built into ignored `.data/package-validation`; Docker images were not rebuilt |
| Ruff | Passed | Backend and local model-check script lint/format |
| TypeScript and Vite production build | Passed | All frontend pages compile |
| Base/cloud Compose configuration | Passed | Configuration parses; secrets were not printed |
| Isolated acceptance Compose override | Passed | Separate project-scoped Neo4j volumes and control/upload/evaluation directory; shared embedding cache; Compose >=2.24.4 |
| Existing production services | Reachable | Neo4j, native vector index, actual cached CPU embeddings and dashboard respond; inference health correctly remains degraded for missing weights |
| Persistence | Passed | Original document IDs/status/provenance, source hashes, graph statistics and evaluation IDs match the retained pre-migration manifest after backend restart |
| Gitleaks working tree/history | Zero findings | All publication candidates and Git history scanned, with ignored local data excluded |
| npm dependency audit | Zero vulnerabilities | Full frontend dependency graph |
| Python dependency audit | No known vulnerabilities in audited packages | Editable local project and CPU-specific Torch build are excluded, as detailed below |

The existing Docker images were reused without rebuilding during this strategy change. New local builds use the committed source. No extra model was downloaded in this phase.

## Pending and historical checks

- **Real `qwen3:4b` inference, schema adherence, entity/relationship quality, grounded answers, citation semantics and end-to-end acceptance:** not passed. No model weights are installed in the cloud runtime.
- **Real-model vector versus hybrid benchmark accuracy/latency/token results:** unavailable. No superiority claim is made.
- **Native Apple Silicon memory/latency:** not measured on this Linux executor.
- Two opt-in live backend checks are excluded from this publication suite. Earlier explicit attempts failed missing-model readiness assertions before inference; those failures were not converted into passes.
- Historical demonstration documents/evaluations remain with original provenance. They predate the Ollama migration and are not live LLM evidence.

Ollama 0.40.9 was installed from its official release with an archive SHA-256 check and a CPU runtime. Both requested registry tags previously returned manifests, but weight downloads were interrupted. Recovery also left a stale proxy binding in the runtime container. This was inspected; no active pull process remained and no retry was started. Defaulting both independently configurable model settings to `qwen3:4b` avoids needing a second model on the local Mac.

Ollama's JSON-schema `format` and streaming protocol are exercised by MockTransport tests; actual Qwen3 adherence is **not** inferred from them. Run the real opt-in check and HTTP acceptance locally as described in [macOS acceptance](macos-local-acceptance.md).

## Reproduce non-LLM checks

```bash
bash scripts/check.sh
```

For integration, set `TEST_NEO4J_URI` and `TEST_NEO4J_PASSWORD` to a separate, empty Neo4j instance, then run:

```bash
.venv/bin/python -m pytest -q -m integration -k 'not live_sentence'
```

The database stores a test-only embedding-model identity. Never point fixtures at the development database or a real-embedding acceptance database. Do not run the browser fixture and integration suite concurrently against the same database.

For browser checks, after integration completes, run the dedicated fixture server and Vite in separate terminals:

```bash
.venv/bin/uvicorn backend.tests.browser_server:app --host 127.0.0.1 --port 8010
GRAPHMIND_API_TARGET=http://127.0.0.1:8010 npm --prefix frontend run dev
# Another terminal:
cd frontend
CHROMIUM_PATH=/usr/bin/chromium npx playwright test
```

On macOS, install Playwright's Chromium and omit `CHROMIUM_PATH`. This server is explicitly test-only and must never stand in for real acceptance. Its scripted known answers are not model-quality measurements.

## Security scope

Gitleaks 8.24.3's release archive was checked against the official SHA-256 list. The scan covers tracked files, nonignored untracked publication candidates and all Git history. `.env`, source uploads, databases, weights, generated exports, private runtime keys and logs are not candidates. `.gitignore` also excludes build/test artifacts. Source/data review remains necessary; pattern scanning does not prove that every sensitive string is detectable.

`pip-audit` could not look up `torch 2.14.1+cpu` in its PyPI advisory source and skipped editable GraphMind. This is an explicit coverage gap, not a clean audit claim for Torch or custom code. The CPU build originates from the configured official PyTorch wheel index in the lockfile. No known detected vulnerability or credential finding is left unresolved.

GitHub identity was verified with an actual `gh api user --jq .login` response. Local and remote history were compared; existing remote commits must remain ancestors of publication. The existing public repository is reused, with no force push. A remote push is called successful only after its commit and source tree are verified.
