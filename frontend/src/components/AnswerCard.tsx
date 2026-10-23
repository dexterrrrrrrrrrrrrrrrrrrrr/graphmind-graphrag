import { Clock3, FileText, GitBranch, Sparkles } from "lucide-react";
import type { Answer } from "../types";
import { modes } from "../types";
import { metric } from "../services/api";
import { Card } from "./ui/card";
import { Link } from "react-router-dom";
import { Badge } from "./Common";
export function AnswerCard({ answer }: { answer: Answer }) {
  return (
    <Card className="answer-card">
      <div className="answer-header">
        <span className="accent">
          <Sparkles size={17} /> GraphMind
        </span>
        <Badge>{modes[answer.strategy]}</Badge>
      </div>
      <p className="answer-text">{answer.answer}</p>
      <div className="muted small">
        {answer.provider} · {answer.model} · {answer.routing_reason}
      </div>
      {answer.fallback && (
        <div className="error">Fallback: {answer.fallback}</div>
      )}
      {answer.warnings.map((w) => (
        <p className="notice" key={w}>
          {w}
        </p>
      ))}
      {!!answer.paths.length && (
        <details open>
          <summary>
            <GitBranch size={15} /> Database reasoning paths (
            {answer.paths.length})
          </summary>
          <Link
            className="accent small"
            to="/graph"
            state={{ paths: answer.paths }}
          >
            Highlight these paths in the graph explorer ↗
          </Link>
          <div className="paths">
            {answer.paths.map((p, i) => (
              <div key={i} className="path">
                {p.nodes.map((n, j) => (
                  <span key={n.id}>
                    {j > 0 && (
                      <small title={p.edges[j - 1]?.evidence}>
                        {" "}
                        {p.edges[j - 1]?.source === p.nodes[j - 1]?.id
                          ? "→"
                          : "←"}{" "}
                        {p.edges[j - 1]?.type.replaceAll("_", " ")}{" "}
                      </small>
                    )}
                    <b>{n.name}</b>
                  </span>
                ))}
              </div>
            ))}
          </div>
          <p className="muted small">
            Arrows above show traversal order. Stored semantic direction is
            shown in relationship details.
          </p>
        </details>
      )}
      <details open>
        <summary>
          <FileText size={15} /> Verified source citations (
          {answer.citations.length})
        </summary>
        <div className="citations">
          {answer.citations.map((c, i) => (
            <div className="citation" key={c.chunk_id}>
              <a href={`/api/documents/${c.document_id}/source`}>
                <span className="citation-number">{i + 1}</span>
                {c.document_name}
                {c.page ? ` · page ${c.page}` : ""}
              </a>
              <p>{c.text}</p>
              <code>{c.chunk_id.slice(0, 12)}</code>
            </div>
          ))}
        </div>
      </details>
      <details>
        <summary>All retrieved evidence ({answer.evidence.length})</summary>
        {answer.evidence.map((e) => (
          <div className="evidence" key={e.chunk_id}>
            <b>{e.document_name}</b>
            <span>
              {e.sources.join(" + ")} · score {e.score.toFixed(4)}
            </span>
            <p>{e.text}</p>
          </div>
        ))}
      </details>
      <div className="answer-footer">
        <span>
          <Clock3 size={14} />
          {metric(answer.latency_ms, " ms")} total ·{" "}
          {metric(answer.retrieval_ms, " ms")} retrieval
        </span>
        <span>
          {answer.token_usage
            ? `${answer.token_usage.input_tokens + answer.token_usage.output_tokens} tokens`
            : "Token usage unavailable"}{" "}
          ·{" "}
          {answer.estimated_cost_usd == null
            ? "Cost unavailable"
            : `API cost $${answer.estimated_cost_usd.toFixed(6)} (hardware excluded)`}
        </span>
      </div>
    </Card>
  );
}
