import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { FlaskConical, Play, Download, Loader2 } from "lucide-react";
import { post, api, metric } from "../services/api";
import type { Answer, Benchmark } from "../types";
import { PageHeading, ErrorBox, Badge, Empty } from "../components/Common";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { AnswerCard } from "../components/AnswerCard";
export function Lab() {
  const [question, setQuestion] = useState("");
  const compare = useMutation({
    mutationFn: () =>
      post<Record<"vector" | "hybrid", Answer>>("/query/compare", { question }),
  });
  const results = useQuery({
    queryKey: ["benchmarks"],
    queryFn: () => api<Benchmark[]>("/evaluation/results"),
  });
  const run = useMutation({
    mutationFn: () => post<Benchmark>("/evaluation/run", {}),
    onSuccess: () => results.refetch(),
  });
  return (
    <>
      <PageHeading
        eyebrow="EVALUATION / COMPARISON LAB"
        title="Put retrieval to the test."
        description="Same question. Same answer model. Two evidence retrieval strategies."
        action={
          <Badge>
            <FlaskConical size={13} /> Measured, not assumed
          </Badge>
        }
      />
      <Card>
        <form
          className="compare-form"
          onSubmit={(e) => {
            e.preventDefault();
            compare.mutate();
          }}
        >
          <input
            aria-label="Comparison question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Enter a multi-hop question…"
            minLength={3}
            required
          />
          <Button disabled={compare.isPending}>
            {compare.isPending ? (
              <Loader2 size={16} className="spin" />
            ) : (
              <Play size={16} />
            )}
            Compare strategies
          </Button>
        </form>
        <p className="muted small">
          Both runs use one settings snapshot. Retrieval failures are reported;
          no mode fallback is allowed.
        </p>
      </Card>
      <ErrorBox error={compare.error} />
      <div className="comparison-grid">
        {(["vector", "hybrid"] as const).map((mode) => (
          <div key={mode}>
            <div className="section-heading">
              <h2>
                {mode === "vector" ? "Standard vector RAG" : "Hybrid GraphRAG"}
              </h2>
              <Badge>
                {mode === "vector" ? "Similarity only" : "Vectors + graph"}
              </Badge>
            </div>
            {compare.data ? (
              <AnswerCard answer={compare.data[mode]} />
            ) : (
              <Card>
                <Empty>
                  Run a comparison to see actual evidence and measured latency.
                </Empty>
              </Card>
            )}
          </div>
        ))}
      </div>
      <div className="section-heading">
        <div>
          <h2>Reproducible benchmark</h2>
          <p className="muted small">
            Upload the complete demo corpus first. Accuracy uses normalized
            reference containment, not an LLM judge.
          </p>
        </div>
        <Button
          variant="outline"
          disabled={run.isPending}
          onClick={() => run.mutate()}
        >
          {run.isPending ? (
            <Loader2 size={16} className="spin" />
          ) : (
            <Play size={16} />
          )}
          Run benchmark
        </Button>
      </div>
      <ErrorBox error={run.error ?? results.error} />
      {results.data?.length ? (
        results.data.map((result) => (
          <Card key={result.id} className="table-card">
            <div className="section-heading">
              <div>
                <h3>{result.dataset_version}</h3>
                <span className="muted small">
                  {new Date(result.created_at).toLocaleString()} ·{" "}
                  {result.provider} / {result.model}
                </span>
              </div>
              <div className="flex gap-3">
                {["json", "csv"].map((format) => (
                  <a
                    key={format}
                    href={`/api/evaluation/results/${result.id}/export?format=${format}`}
                    className="download"
                  >
                    <Download size={14} />
                    {format.toUpperCase()}
                  </a>
                ))}
              </div>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Question</th>
                    <th>Mode</th>
                    <th>Status</th>
                    <th>Accuracy</th>
                    <th>Recall</th>
                    <th>Citations</th>
                    <th>Path</th>
                    <th>Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((r) => (
                    <tr key={r.question_id + r.mode}>
                      <td title={r.question}>
                        {r.question_id} · {r.required_hops} hops
                      </td>
                      <td>{r.mode}</td>
                      <td>{r.status === "failed" ? r.error : "Executed"}</td>
                      {[
                        "answer_accuracy",
                        "evidence_recall",
                        "citation_correctness",
                        "graph_path_correctness",
                      ].map((k) => (
                        <td key={k}>{metric(r.metrics?.[k])}</td>
                      ))}
                      <td>{metric(r.metrics?.latency_ms, " ms")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ))
      ) : (
        <Card>
          <Empty>
            No experiments yet. Results will be persisted and available for
            export.
          </Empty>
        </Card>
      )}
    </>
  );
}
