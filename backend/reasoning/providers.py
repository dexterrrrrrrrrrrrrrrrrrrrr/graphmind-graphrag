"""Local Ollama protocol. No cloud credentials, model pulling, or provider fallback."""

import json
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import TypeVar

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.core.config import Settings

T = TypeVar("T", bound=BaseModel)
_INFERENCE_LOCK = RLock()


class ProviderError(RuntimeError):
    pass


@dataclass
class Completion:
    value: BaseModel
    usage: dict[str, int] | None = None


def retryable(error):
    return isinstance(error, httpx.TransportError) or (
        isinstance(error, httpx.HTTPStatusError)
        and (error.response.status_code == 429 or error.response.status_code >= 500)
    )


class Provider:
    def __init__(self, settings: Settings, transport=None, progress=None):
        self.settings, self.transport, self.progress = settings, transport, progress

    def client(self, timeout=None):
        # Local inference must not be sent through an Internet HTTP proxy.
        return httpx.Client(
            base_url=self.settings.ollama_base_url.rstrip("/") + "/",
            timeout=timeout or self.settings.request_timeout,
            transport=self.transport,
            trust_env=False,
            follow_redirects=False,
        )

    def models(self):
        with self.client(5) as client:
            response = client.get("api/tags")
            response.raise_for_status()
            # Ollama cloud entries can appear in tags; never offer them for local inference.
            return [
                m
                for m in response.json().get("models", [])
                if not m.get("remote_host")
                and not m.get("remote_model")
                and "cloud" not in m.get("name", "").casefold()
            ]

    def status(self):
        s = self.settings
        try:
            models = self.models()
            names = {m.get("name", m.get("model")) for m in models}
            with self.client(5) as client:
                response = client.get("api/ps")
                response.raise_for_status()
                loaded = response.json().get("models", [])
            missing = sorted({s.llm_model, s.extraction_model} - names)
            return {
                "connected": True,
                "ready": not missing,
                "provider": "ollama",
                "answer_model": s.llm_model,
                "extraction_model": s.extraction_model,
                "models": models,
                "loaded_models": loaded,
                "missing_models": missing,
                "message": "Ready for local inference"
                if not missing
                else "Install the missing models with Ollama, or select installed models in Settings.",
            }
        except (httpx.HTTPError, ValueError, KeyError):
            return {
                "connected": False,
                "ready": False,
                "provider": "ollama",
                "answer_model": s.llm_model,
                "extraction_model": s.extraction_model,
                "models": [],
                "loaded_models": [],
                "missing_models": [],
                "message": "Ollama is unavailable. Start Ollama and check the backend's local endpoint.",
            }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception(retryable),
        reraise=True,
    )
    def json(self, system: str, data: dict, schema: type[T], model=None) -> Completion:
        s = self.settings
        chosen = model or s.llm_model
        with _INFERENCE_LOCK:
            names = {m.get("name", m.get("model")) for m in self.models()}
            if chosen not in names:
                raise ProviderError(
                    f"Local Ollama model '{chosen}' is not installed. Install it manually or choose an installed model. No model was downloaded."
                )
            if self.progress:
                self.progress("loading", {"model": chosen})
            started = monotonic()
            with self.client() as client:
                with client.stream(
                    "POST",
                    "api/chat",
                    json={
                        "model": chosen,
                        "stream": True,
                        "think": False,
                        "format": schema.model_json_schema(),
                        "keep_alive": s.ollama_keep_alive,
                        "options": {
                            "temperature": 0,
                            "num_predict": s.max_output_tokens,
                            "num_ctx": s.ollama_context_length,
                        },
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
                        ],
                    },
                ) as response:
                    response.raise_for_status()
                    parts, total, done, counts = [], 0, False, None
                    for line in response.iter_lines():
                        if monotonic() - started > s.request_timeout:
                            raise ProviderError("Ollama inference exceeded the request timeout")
                        if not line:
                            continue
                        payload = json.loads(line)
                        if payload.get("error"):
                            raise ProviderError(
                                "Ollama inference failed; check model compatibility and available memory."
                            )
                        content = payload.get("message", {}).get("content", "")
                        total += len(content)
                        if total > 1_000_000:
                            raise ProviderError("Ollama output exceeded the safety limit")
                        parts.append(content)
                        if content and self.progress:
                            # Stream progress, not unverified factual claims or citations.
                            self.progress("generating", {"model": chosen, "characters": total})
                        if payload.get("done"):
                            done = True
                            if payload.get("done_reason") == "length":
                                raise ProviderError(
                                    "Ollama output was truncated. Increase the output token limit or reduce the context."
                                )
                            counts = {
                                "input_tokens": payload.get("prompt_eval_count", 0),
                                "output_tokens": payload.get("eval_count", 0),
                            }
                    if not done:
                        raise ProviderError("Ollama stream ended before completion; no answer was accepted")
            return Completion(schema.model_validate_json("".join(parts)), counts)
