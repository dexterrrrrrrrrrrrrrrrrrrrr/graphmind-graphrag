"""User-opted live provider contract check; excluded from normal CI. Local inference only."""

import os

import pytest

from backend.core.config import Settings
from backend.knowledge_graph.extraction import extract
from backend.models.schemas import Extraction
from backend.reasoning.providers import Provider

pytestmark = pytest.mark.live


def test_authorized_live_extraction():
    if os.getenv("GRAPHMIND_RUN_LIVE_LLM") != "1":
        pytest.skip("Requires explicit GRAPHMIND_RUN_LIVE_LLM=1; requires installed local Ollama models")
    settings = Settings()
    assert Provider(settings).status()["ready"], "Local Ollama and configured models must be available"
    result = extract("AlphaTech acquired DataVision.", Provider(settings), settings)
    assert isinstance(result, Extraction)
    assert any(r.type == "ACQUIRED" for r in result.relationships)
