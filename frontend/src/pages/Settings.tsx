import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Save, ShieldCheck } from "lucide-react";
import { api } from "../services/api";
import { type Settings as Data, type OllamaStatus, modes } from "../types";
import { PageHeading, ErrorBox, Loading, Badge } from "../components/Common";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
export function Settings() {
  const q = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Data>("/settings"),
  });
  const ollama = useQuery({ queryKey: ["ollama"], queryFn: () => api<OllamaStatus>("/ollama/status"), refetchInterval: 15000 });
  const [form, setForm] = useState<Data | null>(null);
  useEffect(() => {
    if (q.data) setForm(q.data);
  }, [q.data]);
  const save = useMutation({
    mutationFn: () => {
      const keys = [
        "extraction_model",
        "ollama_context_length",
        "request_timeout",
        "llm_model",
        "top_k",
        "max_depth",
        "similarity_threshold",
        "chunk_size",
        "chunk_overlap",
        "context_tokens",
        "reranking",
        "fusion",
        "vector_weight",
        "default_mode",
      ] as const;
      const body = Object.fromEntries(keys.map((key) => [key, form![key]]));
      return api<Data>("/settings", {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => q.refetch(),
  });
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE / SETTINGS"
        title="Tune your research engine."
        description="Changes apply to future requests. Reprocess documents to update chunking or extraction."
        action={
          <Badge>
            <ShieldCheck size={14} /> Local inference · no API keys
          </Badge>
        }
      />
      <ErrorBox error={q.error ?? save.error} />
      {!form ? (
        <Loading />
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <Card>
            <h2>Local Ollama models</h2>
            <p className="muted">Inference runs on your Ollama host. No cloud account or API charges. Models are never downloaded automatically.</p>
            <p role="status" className="notice">{ollama.data?.message ?? "Checking Ollama connection…"}
              {ollama.data?.loaded_models.length ? ` Loaded: ${ollama.data.loaded_models.map(m => m.name).join(", ")}` : ""}
            </p>
            <ErrorBox error={ollama.error} />
            <Button type="button" onClick={() => void ollama.refetch()}>Refresh installed models</Button>
            <div className="form-grid">
              {([ ["llm_model", "Answer model"], ["extraction_model", "Entity and relationship model"] ] as const).map(([key, label]) => (
                <label key={key}>{label}<select value={form[key]} onChange={e => setForm({...form, [key]: e.target.value})}>
                  {!ollama.data?.models.some(m => m.name === form[key]) && <option value={form[key]}>{form[key]} (not available)</option>}
                  {ollama.data?.models.map(m => <option key={m.name} value={m.name}>{m.name} · {(m.size / 1e9).toFixed(1)} GB</option>)}
                </select></label>
              ))}
              <label>Model context window<input type="number" min={2048} max={65536} value={form.ollama_context_length} onChange={e => setForm({...form, ollama_context_length: Number(e.target.value)})} /></label>
              <label>Inference timeout (seconds)<input type="number" min={5} max={1800} value={form.request_timeout} onChange={e => setForm({...form, request_timeout: Number(e.target.value)})} /></label>
            </div>
            <p className="muted small">Default: qwen3:4b for both extraction and answers. Each setting can select a different installed model. If a tag is unavailable, explicitly select another installed local model. The backend serializes requests and unloads models after use to limit memory.</p>
          </Card>
          <Card>
            <h2>Retrieval configuration</h2>
            <div className="form-grid">
              <label>
                Default mode
                <select
                  value={form.default_mode}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      default_mode: e.target.value as Data["default_mode"],
                    })
                  }
                >
                  {Object.entries(modes).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Fusion strategy
                <select
                  value={form.fusion}
                  onChange={(e) => setForm({ ...form, fusion: e.target.value })}
                >
                  <option value="rrf">Reciprocal rank fusion</option>
                  <option value="weighted">Weighted scores</option>
                </select>
              </label>
              {(
                [
                  ["top_k", "Top-K chunks", 1, 30, 1],
                  ["max_depth", "Traversal depth", 1, 5, 1],
                  ["similarity_threshold", "Similarity threshold", -1, 1, 0.01],
                  [
                    "context_tokens",
                    "Conservative context budget",
                    256,
                    32000,
                    1,
                  ],
                  ["vector_weight", "Vector fusion weight", 0, 1, 0.05],
                ] as const
              ).map(([key, label, min, max, step]) => (
                <label key={key}>
                  {label}
                  <input
                    type="number"
                    required
                    min={min}
                    max={max}
                    step={step}
                    value={form[key]}
                    onChange={(e) =>
                      setForm({ ...form, [key]: Number(e.target.value) })
                    }
                  />
                </label>
              ))}
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={form.reranking}
                  onChange={(e) =>
                    setForm({ ...form, reranking: e.target.checked })
                  }
                />
                Deterministic lexical context reranking
              </label>
            </div>
          </Card>
          <Card>
            <h2>Document processing</h2>
            <div className="form-grid">
              {(["chunk_size", "chunk_overlap"] as const).map((key) => (
                <label key={key}>
                  {key.replaceAll("_", " ")} (characters)
                  <input
                    type="number"
                    required
                    min={key === "chunk_size" ? 100 : 0}
                    max={key === "chunk_size" ? 8000 : 2000}
                    value={form[key]}
                    onChange={(e) =>
                      setForm({ ...form, [key]: Number(e.target.value) })
                    }
                  />
                </label>
              ))}
              <label>
                Embedding model
                <input readOnly value={form.embedding_model} />
              </label>
            </div>
            <p className="muted small">
              Embedding model changes require a separate database and
              re-ingestion to prevent mixing vector spaces.
            </p>
          </Card>
          <div className="save-row">
            {save.isSuccess && (
              <span className="accent" role="status">
                Settings saved
              </span>
            )}
            <Button disabled={save.isPending}>
              <Save size={16} />
              {save.isPending ? "Saving…" : "Save configuration"}
            </Button>
          </div>
        </form>
      )}
    </>
  );
}
