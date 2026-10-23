# GraphMind implementation status

The existing application is implemented with Ollama-only runtime inference, local Sentence Transformers and Neo4j hybrid retrieval. The seven dashboard pages, ingestion, graph explorer, baseline/comparison lab, analytics, evaluation framework, provenance and persistent stores are preserved.

**Initial publication uses non-LLM and mocked-inference quality gates. Real-model GraphRAG acceptance remains pending.** Do not describe this release as an end-to-end validated real-model system or claim benchmark superiority.

Both independently configurable defaults are `qwen3:4b` (`EXTRACTION_MODEL`, `LLM_MODEL`). This uses one local weight installation by default. Installed local models may be selected separately. Paid providers/API keys and deterministic production inference are absent. Ollama discovery/health, JSON-schema transport, streaming progress, context/timeouts/retries and serialized memory-conscious inference are implemented.

Validated extraction caches, exact source evidence, type-aware entity normalization and relation deduplication preserve provenance. Deleting documents removes their private cached evidence. Paths are database traversal outputs; citation IDs/quotes are checked against retrieved chunks. These checks do not establish semantic entailment or model quality.

## Validated without model weights

- Backend unit/API/protocol tests and isolated real Neo4j plumbing tests, with explicit inference doubles.
- Frontend unit tests, TypeScript, Vite production build and all-seven-page Playwright workflow using those doubles.
- Compose configuration and isolated acceptance override, current service connectivity and persistent document/source/graph/evaluation identity.
- Secret scanning and dependency audits within their documented coverage; CPU-specific Torch advisory lookup remains an explicit gap.

Exact counts and scope are in [docs/validation.md](docs/validation.md). No original documents were reprocessed; no historical evaluations were removed. The requested model setting was updated while other settings were retained.

## Pending local acceptance

Cloud model downloads caused repeated executor disruptions and are no longer attempted. Ollama is installed, but local cloud weights are absent. Follow [docs/macos-local-acceptance.md](docs/macos-local-acceptance.md) to install native Ollama and `qwen3:4b`, check real schema-constrained extraction, start the normal application and a separate acceptance project, and run the actual three-document HTTP workflow, hop checks, citations and measured benchmark.

`scripts/check_local_model.py` and `scripts/demo.py` never use model doubles or pull weights. They fail if required models/evidence are missing. The local commands are provided instructions, not executed cloud results. Sanitized measured results can be committed in a later update after local success.
