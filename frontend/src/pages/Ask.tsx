import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowUp, MessageSquare, Network, Loader2 } from "lucide-react";
import { streamQuestion, api } from "../services/api";
import { type Answer, type Mode, type Settings, modes } from "../types";
import { PageHeading, ErrorBox, Empty } from "../components/Common";
import { Button } from "../components/ui/button";
import { AnswerCard } from "../components/AnswerCard";
export function Ask() {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<Mode>("auto");
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/settings"),
  });
  useEffect(() => {
    if (settings.data) setMode(settings.data.default_mode);
  }, [settings.data]);
  const [messages, setMessages] = useState<Answer[]>([]);
  const history = useQuery({
    queryKey: ["history"],
    queryFn: () => api<Answer[]>("/queries?limit=15"),
  });
  const [progress, setProgress] = useState("");
  const ask = useMutation({
    mutationFn: () => streamQuestion<Answer>({ question, mode }, setProgress),
    onSuccess: (a) => {
      setMessages((m) => [...m, a]);
      setQuestion("");
      void history.refetch();
    },
  });
  return (
    <>
      <PageHeading
        eyebrow="RESEARCH / QUESTION ANSWERING"
        title="Ask across your knowledge."
        description="Trace answers through documents, entities, and the relationships between them."
      />
      <div className="ask-layout">
        <div>
          <div className="conversation">
            {!messages.length && (
              <Empty>
                <Network size={44} />
                <h2>One question. Connected evidence.</h2>
                <p>Try a question that requires more than one document.</p>
                <button
                  className="suggestion"
                  onClick={() =>
                    setQuestion(
                      "Which organization is indirectly connected to Rahul Sharma through his company's acquisition and subsequent partnership?",
                    )
                  }
                >
                  Explore the three-hop demonstration →
                </button>
              </Empty>
            )}
            {messages.map((m) => (
              <div key={m.id}>
                <div className="question-bubble">
                  <MessageSquare size={16} />
                  {m.question}
                </div>
                <AnswerCard answer={m} />
              </div>
            ))}
          </div>
          {ask.isPending && <p role="status" className="notice">{progress || "Waiting for local inference…"}</p>}
          <ErrorBox error={ask.error} />
          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              if (question.trim().length >= 3 && !ask.isPending) ask.mutate();
            }}
          >
            <textarea
              aria-label="Your question"
              placeholder="Ask a question about your documents…"
              value={question}
              maxLength={4000}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <div>
              <select
                aria-label="Retrieval mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as Mode)}
              >
                {Object.entries(modes).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <span className="muted small">Grounded in your sources</span>
              <Button
                type="submit"
                aria-label="Send question"
                disabled={ask.isPending || question.trim().length < 3}
              >
                {ask.isPending ? (
                  <Loader2 className="spin" size={18} />
                ) : (
                  <ArrowUp size={18} />
                )}
              </Button>
            </div>
          </form>
        </div>
        <aside className="history-panel">
          <h3>Query history</h3>
          <ErrorBox error={history.error} />
          {history.data?.length ? (
            history.data.map((m) => (
              <button key={m.id} onClick={() => setMessages([m])}>
                <MessageSquare size={14} />
                <span>
                  {m.question}
                  <small>
                    {modes[m.strategy]} · {m.latency_ms.toFixed(0)} ms
                  </small>
                </span>
              </button>
            ))
          ) : (
            <p className="muted small">Your research trail will appear here.</p>
          )}
        </aside>
      </div>
    </>
  );
}
