import json
import re

from backend.retrieval.fusion import budget, fuse, rerank
from backend.retrieval.router import route


class Retriever:
    def __init__(self, graph, embedder):
        self.graph, self.embedder = graph, embedder

    def retrieve(self, request, settings):
        strategy, reason = (
            route(request.question) if request.mode == "auto" else (request.mode, "User override")
        )
        k = request.top_k or settings.top_k
        depth = request.max_depth or settings.max_depth
        vector, graph_evidence, paths = [], [], []
        if strategy in ("vector", "hybrid"):
            vector = self.graph.vector(
                self.embedder.embed_query(request.question), k, settings.similarity_threshold
            )
        if strategy in ("graph", "hybrid"):
            ids = self.graph.link(request.question)
            paths = self.graph.traverse(ids, depth, settings.path_limit) if ids else []
            terms = set(re.findall(r"\w+", request.question.casefold()))
            for p in paths:
                labels = " ".join(e.type.replace("_", " ").lower() for e in p.edges)
                p.score = sum(e.confidence for e in p.edges) / len(p.edges) + 0.15 * len(p.edges)
                p.score += len(terms & set(labels.split())) / max(len(terms), 1)
            paths = sorted(paths, key=lambda p: (-p.score, tuple(e.id for e in p.edges)))[
                : settings.path_limit
            ]
            chunk_ids = list(dict.fromkeys(e.chunk_id for p in paths for e in p.edges))
            by_id = {e.chunk_id: e for e in self.graph.evidence(chunk_ids)}
            for i, id in enumerate(chunk_ids):
                if id in by_id:
                    graph_evidence.append(by_id[id].model_copy(update={"score": 1 / (i + 1)}))
        if strategy == "vector":
            evidence = vector
        elif strategy == "graph":
            evidence = graph_evidence
        else:
            evidence = fuse(vector, graph_evidence, settings.fusion, settings.vector_weight)
        if settings.reranking:
            evidence = rerank(request.question, evidence)
        from backend.reasoning.answers import ANSWER_SYSTEM, AnswerOutput

        overhead = (
            len(
                (ANSWER_SYSTEM + json.dumps(AnswerOutput.model_json_schema()) + request.question).encode(
                    "utf-8"
                )
            )
            + 150
        )
        available = max(0, settings.context_tokens - overhead)
        evidence = budget(evidence, available)
        retained = {e.chunk_id for e in evidence}
        # Display only paths whose every supporting chunk was supplied to the generator.
        paths = [p for p in paths if all(e.chunk_id in retained for e in p.edges)]
        remaining = max(
            0,
            available
            - len(json.dumps([e.model_dump() for e in evidence], ensure_ascii=False).encode("utf-8")),
        )
        retained_paths = []
        for path in paths:
            size = len(json.dumps(path.model_dump(), ensure_ascii=False).encode("utf-8")) + 2
            if size <= remaining:
                retained_paths.append(path)
                remaining -= size
        return strategy, reason, evidence, retained_paths
