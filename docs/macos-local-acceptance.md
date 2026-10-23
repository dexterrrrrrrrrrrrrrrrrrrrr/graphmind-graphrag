# macOS: real Ollama acceptance

These commands are instructions, **not a record of a successful run**. Use native Ollama on Apple Silicon, Docker Desktop with Compose >=2.24.4, Homebrew and sufficient disk/RAM (16 GB RAM recommended). The cloud tests do not establish model quality. Only one `qwen3:4b` weight installation is needed; extraction and answer settings remain independent.

## 1. Install and start native Ollama

```bash
brew install --cask ollama
brew install uv
launchctl setenv OLLAMA_HOST 0.0.0.0:11434
launchctl setenv OLLAMA_NO_CLOUD 1
launchctl setenv OLLAMA_MAX_LOADED_MODELS 1
launchctl setenv OLLAMA_NUM_PARALLEL 1
open -a Ollama
```

If Ollama was already running, quit and reopen it after `launchctl setenv`. Host binding makes it reachable by Docker; use the macOS firewall to restrict untrusted clients because Ollama has no authentication by default. No Ollama cloud account is needed.

Check resources before the explicit download:

```bash
df -h .
sysctl -n hw.memsize
ollama pull qwen3:4b
ollama list
curl -fsS http://localhost:11434/api/version
curl -fsS http://localhost:11434/api/tags
```

Do not proceed until the tag appears locally. Cloud weight downloads are intentionally not part of the publication workflow.

## 2. Prepare the existing implementation

Skip `git clone` if you already have the checkout; do not overwrite existing files.

```bash
git clone https://github.com/dexterrrrrrrrrrrrrrrrrrrrr/graphmind-graphrag.git
cd graphmind-graphrag
uv python install 3.12
uv sync --python 3.12 --frozen --extra dev
.venv/bin/python scripts/init_env.py
```

`init_env.py` preserves an existing `.env`; otherwise it creates one with a random local Neo4j password. Confirm these nonsecret values in `.env`:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:4b
EXTRACTION_MODEL=qwen3:4b
OLLAMA_BASE_URL=http://localhost:11434
```

No API key is required. Existing persisted Settings selections take precedence for future jobs, so verify them in the Settings page. Do not alter existing retrieval preferences unnecessarily.

## 3. Check real structured extraction before ingestion

```bash
.venv/bin/python -m scripts.check_local_model --output .data/local-model-check.json
cat .data/local-model-check.json
```

This is an actual inference check, not a fixture: it calls the configured extraction model with a Pydantic JSON schema, verifies the directed `Rahul Sharma → FOUNDED → AlphaTech` fact and verbatim evidence, then calls the answer model and verifies source citation/quotes. It writes measured timings and reported token usage. Any error means model/schema compatibility or grounding is not yet verified; do not call acceptance successful.

## 4. Start GraphMind

Ensure Docker Desktop is running:

```bash
docker compose up --build -d
docker compose ps
curl -fsS http://localhost:8000/api/ollama/status
curl -fsS http://localhost:8000/api/health
open http://localhost:3000
```

Compose overrides the native URL to `http://host.docker.internal:11434`. The initial Sentence Transformers load may download the public embedding model; embeddings/inference run locally afterward. Health must show Neo4j, vector index, embeddings and model generation ready. Do not treat a PID or open port alone as readiness.

## 5. Use isolated data for genuine acceptance

The following stack has separate Neo4j volumes and `.data/local-acceptance` control/uploads/evaluations, and shares only the embedding cache. It leaves the normal application data intact. Requires Compose >=2.24.4 for `!override`.

```bash
docker compose -p graphmind-acceptance -f docker-compose.yml -f docker-compose.acceptance.yml config --quiet
docker compose -p graphmind-acceptance -f docker-compose.yml -f docker-compose.acceptance.yml up --build -d
curl -fsS http://localhost:8011/api/health
.venv/bin/python scripts/demo.py --api http://localhost:8011/api --output .data/local-acceptance-report
```

Wait for health readiness before the script. It uploads the three actual files, requires Ollama processing provenance, waits for embedding/graph/index completion, checks the hybrid answer **MedCore**, all three uploaded source document IDs, and the ordered **Rahul Sharma → AlphaTech → DataVision → MedCore** database path. The vector baseline must have no graph paths or fallback. It then runs all benchmark questions and saves real JSON/CSV results. Completed requests do not imply correct answers: inspect the recorded metrics and failures.

Rerunning without `--reprocess` reuses already ingested bytes. For a fresh inference experiment, use a fresh isolated project/directory or explicitly reprocess only this acceptance stack. Do not reprocess the main application's documents to validate it.

## 6. Inspect actual graph evidence and hop limits

```bash
curl -fsS http://localhost:8011/api/documents
curl -fsS http://localhost:8011/api/graph/stats
curl -fsS http://localhost:8011/api/graph/entities
curl -fsS http://localhost:8011/api/graph/subgraph
open http://localhost:3001/graph
```

Expected facts: `FOUNDED`, `ACQUIRED`, `PARTNERED_WITH`. Each edge must retain its real chunk/document IDs and exact source excerpt. In the graph explorer, inspect relationship provenance.

For explicit one-/two-/three-hop requests:

```bash
.venv/bin/python - <<'PY'
import httpx
checks = [
    (1, 'Who founded AlphaTech?', 'Rahul Sharma'),
    (2, 'Which company did the company founded by Rahul Sharma acquire through its acquisition?', 'DataVision'),
    (3, "Which organization is indirectly connected to Rahul Sharma through his company's acquisition and subsequent partnership?", 'MedCore'),
]
with httpx.Client(base_url='http://localhost:8011/api', timeout=1800, trust_env=False) as c:
    for hops, question, expected in checks:
        r = c.post('/query', json={'question': question, 'mode': 'hybrid', 'max_depth': hops})
        r.raise_for_status()
        result = r.json()
        assert expected in result['answer'], result
        assert result['citations'], result
        assert any(len(p['edges']) == hops for p in result['paths']), result
        assert all(len(p['edges']) <= hops for p in result['paths']), result
        print(hops, result['answer'], result['latency_ms'], 'ms')
PY
```

These assertions are pending until you execute them. Inspect the response quotes/source downloads too: ID/quote validation is not a semantic entailment judge.

## 7. Review citations and benchmark measurements

```bash
open http://localhost:3001/ask
open http://localhost:3001/lab
open http://localhost:3001/analytics
curl -fsS http://localhost:8011/api/evaluation/summary
curl -fsS http://localhost:8011/api/evaluation/results
```

The demo script already ran the benchmark. Use the lab to compare another question or explicitly rerun `POST /api/evaluation/run`. Both modes use identical answer model settings. Review one-/two-/three-hop and unanswerable rows, evidence recall, citation relevance, directed path correctness, latency and Ollama token counts. API cost is zero and excludes hardware/electricity. Do not invent a hybrid performance gain.

Artifacts: `.data/local-model-check.json`, `.data/local-acceptance-report.json`, `.data/local-acceptance-report.csv`. They are ignored because results can contain source text. After successful local acceptance, add a sanitized measured-results summary to `docs/validation.md`, including model tag/digest, hardware, settings, timestamp, failures and metric limitations, then commit/push that documentation separately. Never publish your private documents, `.env`, databases, model weights or raw private-source reports.

Stop only the isolated stack when finished; retain its data:

```bash
docker compose -p graphmind-acceptance -f docker-compose.yml -f docker-compose.acceptance.yml down
```

Do not add `-v` when preserving Neo4j volumes.
