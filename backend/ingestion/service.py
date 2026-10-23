import hashlib
import json
import logging
from pathlib import Path

from backend.core.store import now
from backend.ingestion.parsing import chunk_pages, parse
from backend.knowledge_graph.extraction import extract, validate_extraction
from backend.models.schemas import Extraction
from backend.reasoning.providers import Provider

log = logging.getLogger(__name__)


class Ingestor:
    def __init__(self, store, graph, embedder):
        self.store, self.graph, self.embedder = store, graph, embedder

    def run(self, document_id, settings):
        document = self.store.document(document_id)
        if not document:
            return
        existing_graph = bool(self.graph.read("MATCH (d:Document {id:$id}) RETURN d.id", id=document_id))
        try:
            self.store.processing_metadata(document_id, settings)
            self.store.update_document(document_id, "parsing", 5)
            data = (self.store.directory / "uploads" / document_id).read_bytes()
            pages = parse(data, Path(document["name"]).suffix.lower())
            chunks = chunk_pages(pages, document_id, settings.chunk_size, settings.chunk_overlap)
            self.store.update_document(document_id, "embedding", 20, len(chunks))
            vectors = self.embedder.embed([c["text"] for c in chunks])
            self.store.update_document(document_id, "extracting", 45, len(chunks))
            provider = Provider(settings)
            extractions = []
            for i, chunk in enumerate(chunks):
                cache_key = hashlib.sha256(
                    json.dumps(
                        {
                            "text": chunk["text"],
                            "model": settings.extraction_model,
                            "types": settings.relationship_types,
                            "context": settings.ollama_context_length,
                            "prompt_version": "ollama-v2",
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                cached = self.store.extraction_cache(cache_key, document_id=document_id)
                value = (
                    validate_extraction(
                        Extraction.model_validate(cached), chunk["text"], settings.relationship_types
                    )
                    if cached is not None
                    else extract(chunk["text"], provider, settings)
                )
                if cached is None:
                    self.store.extraction_cache(cache_key, value.model_dump(), document_id=document_id)
                extractions.append(value)
                chunk.update(
                    embedding=vectors[i], embedding_model=self.embedder.model_name, ingested_at=now()
                )
                self.store.update_document(
                    document_id, "extracting", 45 + int(40 * (i + 1) / len(chunks)), len(chunks)
                )
            self.store.update_document(document_id, "indexing", 90, len(chunks))
            self.graph.persist(document, chunks, extractions)
            self.store.purge_evidence(document_id)
            self.store.update_document(document_id, "ready", 100, len(chunks))
            log.info("ingestion_complete document=%s chunks=%s", document_id, len(chunks))
        except Exception as error:
            try:
                if not existing_graph:
                    self.graph.delete(document_id)
            except Exception:
                log.error("failed_ingestion_cleanup_pending document=%s", document_id)
            # Avoid leaking provider request URLs/credentials through frontend error messages.
            log.error("ingestion_failed document=%s error_type=%s", document_id, type(error).__name__)
            detail = (
                str(error)
                if isinstance(error, ValueError)
                else type(error).__name__ + ": ingestion failed; inspect service readiness"
            )
            self.store.update_document(document_id, "failed", 0, error=detail[:800])
