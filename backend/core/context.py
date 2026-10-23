from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock, RLock
from time import monotonic

from backend.core.config import Settings
from backend.core.store import Store
from backend.embeddings.service import Embedder
from backend.evaluation.service import Evaluator
from backend.ingestion.service import Ingestor
from backend.knowledge_graph.repository import GraphRepository
from backend.reasoning.service import QueryService
from backend.retrieval.service import Retriever


class Context:
    def __init__(self, settings: Settings):
        self.store = Store(settings.data_dir)
        saved = self.store.saved_settings()
        # Migrate legacy provider settings while retaining retrieval and ingestion preferences.
        if saved.get("llm_provider", "ollama") != "ollama":
            saved.pop("llm_model", None)
        saved["llm_provider"] = "ollama"
        if not saved.get("llm_model", settings.llm_model):
            saved.pop("llm_model", None)
        saved = {k: v for k, v in saved.items() if k in Settings.model_fields}
        self.settings = Settings.model_validate({**settings.model_dump(), **saved})
        self.store.save_settings(saved)
        self.graph = GraphRepository(self.settings)
        self.embedder = Embedder(
            settings.embedding_model, settings.embedding_dimension, settings.data_dir / "models"
        )
        self.ingestor = Ingestor(self.store, self.graph, self.embedder)
        self.query = QueryService(Retriever(self.graph, self.embedder), self.store)
        self.evaluator = Evaluator(
            self.store, self.query, Path(__file__).resolve().parents[2] / "datasets/benchmark.json"
        )
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")
        self.lock = RLock()
        self.graph_ready = False
        self.startup_error = None
        self.embedding_error = None
        self._graph_lock = Lock()
        self._graph_retry_at = 0.0

    def initialize(self):
        self.ensure_graph()
        for doc in self.store.documents():
            if doc["status"] not in ("ready", "failed"):
                self.store.update_document(
                    doc["id"], "failed", 0, error="Processing interrupted; reprocess document"
                )

    def ensure_graph(self):
        """Recover failed schema startup without concurrent retries or changing document jobs."""
        if self.graph_ready or monotonic() < self._graph_retry_at:
            return
        if not self._graph_lock.acquire(blocking=False):
            return
        try:
            if not self.graph_ready and monotonic() >= self._graph_retry_at:
                try:
                    self.graph.initialize()
                    self.graph_ready = True
                    self.startup_error = None
                except Exception as error:
                    self.startup_error = type(error).__name__
                    self._graph_retry_at = monotonic() + 15
        finally:
            self._graph_lock.release()

    def warm_embeddings(self):
        try:
            self.embedder.load()
            self.embedding_error = None
        except Exception as error:
            self.embedding_error = type(error).__name__

    def snapshot(self):
        # Settings updates replace the entire model. Holding the operation lock here
        # would block health/status polling for the duration of local generation.
        return self.settings.model_copy(deep=True)

    def close(self):
        self.executor.shutdown(wait=True)
        self.graph.driver.close()
