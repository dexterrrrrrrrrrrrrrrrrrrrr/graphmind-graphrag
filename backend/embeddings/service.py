import os
import threading
from pathlib import Path

import numpy as np


class Embedder:
    def __init__(self, model_name: str, dimension: int, cache_dir: Path | None = None):
        self.model_name = model_name
        self.dimension = dimension
        self.cache_dir = Path(os.getenv("HF_HOME", str(cache_dir or Path(".data/models"))))
        self._model = None
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            if self._model is None:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                os.environ.setdefault("HF_XET_CACHE", str(self.cache_dir / "xet"))
                import torch

                torch.set_num_threads(min(os.cpu_count() or 1, 4))
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    self.model_name, device="cpu", trust_remote_code=False, cache_folder=str(self.cache_dir)
                )
                dimension = (
                    self._model.get_embedding_dimension()
                    if hasattr(self._model, "get_embedding_dimension")
                    else self._model.get_sentence_embedding_dimension()
                )
                if dimension != self.dimension:
                    self._model = None
                    raise ValueError(
                        "Embedding dimension mismatch; use a separate database when changing models"
                    )
        return self

    @property
    def ready(self):
        return self._model is not None

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.load()
        with self._lock:
            result = self._model.encode(
                texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
            ).tolist()
        if not np.isfinite(result).all():
            raise ValueError("Embedding model produced non-finite values")
        return result

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]
