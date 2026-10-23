# Reproducible evaluation

The built-in dataset is `datasets/benchmark.json`, version `graphmind-chain-v1`. It declares reference answers, question categories, required hops, source filenames (resolved to actual ready document IDs at run time), exact expected excerpts, and directed entity relationships. The corpus facts are manually inspectable. Do not change a dataset without changing its version.

Each run stores a timestamp, immutable provider/model and retrieval settings, complete responses, measured latency, available token usage, optional cost estimates, and execution errors. Both modes use the same settings snapshot and the same generator. The two-hop case explicitly bounds traversal to two hops; the three-hop case uses the configured default depth. There are no mock benchmark results and no mode substitution. `status=completed` means the call executed; accuracy can still be zero. `failed` means no valid response was obtained.

## Measures

| Measure | Definition | Caveat |
| --- | --- | --- |
| Answer accuracy | Normalized reference containment in answer text; local appended supporting quotes excluded | An inspectable heuristic, not a semantic judge |
| Multi-hop accuracy | Mean answer accuracy for questions requiring >=2 hops | Tiny demonstration dataset; not statistically conclusive |
| Evidence recall | Fraction of expected verbatim excerpts found in retrieved chunks from expected documents | Paraphrases do not count; chunk boundaries can affect this |
| Citation correctness | Fraction of returned citations containing an expected reference excerpt | Precision against this dataset, not general entailment |
| Graph path correctness | A returned database path contains every expected directed relation | N/A for vector mode, which deliberately has no graph paths |
| Latency | Full service duration from retrieval through generation | Sequential calls are subject to warm-cache/order effects |
| Token usage | Provider-reported input/output counts | N/A for offline mode or missing usage metadata |
| Estimated cost | Usage × configured per-million-token prices | No inferred or hardcoded price; not a provider invoice |

No citations or no expected evidence makes the corresponding metric `null`, not a made-up perfect score. Unanswerable questions require the exact refusal. Failed rows are counted separately; averages never hide the failed count.

The summary endpoint aggregates retained runs. Compare individual runs with matching provider/model/dataset/settings. The demonstration is too small for claims about superiority. In particular, with top-K=8 all three tiny documents often fit vector context, so both methods may answer correctly. The offline generator is a transparent engineering fixture and cannot establish LLM performance. A meaningful research experiment needs a larger held-out dataset, distractor documents, hop-balanced samples, repeated order-randomized runs, verified extraction, and an independent semantic correctness rubric.

## Run and export

1. Start services and wait for `/api/health` to report ready.
2. Upload all three demo files and wait until each is ready.
3. Run `python scripts/demo.py` or use Comparison Lab → Run benchmark.
4. Read `/api/evaluation/results`, `/api/evaluation/summary`.
5. Download `/api/evaluation/results/{id}/export?format=json` or `format=csv`.

Evaluation never changes providers or downgrades retrieval when a component fails. Live provider runs may incur charges; configure and authorize them deliberately. The implementation task used mocked provider responses and made no paid requests.
