from fastapi import APIRouter, HTTPException, Request

from backend.api.dependencies import ctx
from backend.core.config import Settings
from backend.models.schemas import (
    SettingsPatch,
)

router = APIRouter()


@router.get("/api/settings")
def settings(request: Request) -> dict:
    c = ctx(request)
    s = c.snapshot()
    keys = set(SettingsPatch.model_fields) | {"embedding_model", "relationship_types", "max_upload_mb"}
    return {
        **{k: getattr(s, k) for k in keys},
        "notice": "Local Ollama inference only. Reprocess documents to change extraction. No models are downloaded automatically.",
    }


@router.patch("/api/settings")
def patch_settings(body: SettingsPatch, request: Request) -> dict:
    c = ctx(request)
    with c.lock:
        changes = body.model_dump(exclude_none=True)
        try:
            updated = Settings.model_validate({**c.settings.model_dump(), **changes})
        except ValueError as error:
            raise HTTPException(
                422, "Invalid settings: check overlap, local model names and context limits"
            ) from error
        c.store.save_settings({**c.store.saved_settings(), **changes})
        c.settings = updated
    return settings(request)
