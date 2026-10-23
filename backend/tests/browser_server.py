"""Opt-in browser test server. Never used by the application entrypoint."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from backend.api.main import app
from backend.core.config import Settings
from backend.core.context import Context
from backend.tests.test_integration import FixtureEmbedder


@asynccontextmanager
async def test_lifespan(application):
    uri = os.environ["TEST_NEO4J_URI"]
    assert uri != os.getenv("NEO4J_URI", "bolt://localhost:7687")
    settings = Settings(
        neo4j_uri=uri,
        neo4j_password=os.environ["TEST_NEO4J_PASSWORD"],
        data_dir=Path(".data/browser-tests"),
        llm_provider="ollama",
        embedding_model=FixtureEmbedder.model_name,
        requests_per_minute=500,
    )
    from unittest.mock import patch

    from backend.tests.fixture_provider import FixtureProvider

    # Dedicated test entrypoint only; production routes never select this double.
    extraction_patch = patch("backend.ingestion.service.Provider", FixtureProvider)
    answer_patch = patch("backend.reasoning.service.Provider", FixtureProvider)
    status_patch = patch(
        "backend.reasoning.providers.Provider.status",
        return_value={
            "connected": True,
            "ready": True,
            "provider": "ollama",
            "answer_model": settings.llm_model,
            "extraction_model": settings.extraction_model,
            "models": [
                {"name": name, "size": 100}
                for name in sorted({settings.llm_model, settings.extraction_model})
            ],
            "loaded_models": [],
            "missing_models": [],
            "message": "Test-only model double",
        },
    )
    status_patch.start()
    extraction_patch.start()
    answer_patch.start()
    c = Context(settings)
    c.embedder = FixtureEmbedder()
    c.embedder.ready = True
    c.ingestor.embedder = c.embedder
    c.query.retriever.embedder = c.embedder
    c.initialize()
    assert c.graph_ready
    assert c.graph.stats()["documents"] == 0, "Browser fixtures require an empty dedicated Neo4j instance"
    # Discard stale control records only in this explicitly test-only directory.
    for previous in c.store.documents():
        c.store.purge_evidence(previous["id"])
        c.store.remove_document(previous["id"])
        (c.store.directory / "uploads" / previous["id"]).unlink(missing_ok=True)
    application.state.context = c
    yield
    for d in c.store.documents():
        c.graph.delete(d["id"])
        c.store.remove_document(d["id"])
        (c.store.directory / "uploads" / d["id"]).unlink(missing_ok=True)
    c.close()
    extraction_patch.stop()
    answer_patch.stop()
    status_patch.stop()


app.router.lifespan_context = test_lifespan
