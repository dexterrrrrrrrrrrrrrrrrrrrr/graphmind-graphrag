from fastapi import APIRouter, Request

from backend.api.dependencies import ctx
from backend.reasoning.providers import Provider

router = APIRouter()


@router.get("/api/ollama/status")
def status(request: Request) -> dict:
    return Provider(ctx(request).snapshot()).status()


@router.get("/api/ollama/models")
def models(request: Request) -> dict:
    state = Provider(ctx(request).snapshot()).status()
    return {"connected": state["connected"], "models": state["models"], "message": state["message"]}
