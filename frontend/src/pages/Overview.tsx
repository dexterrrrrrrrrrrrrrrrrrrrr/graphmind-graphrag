import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  FileText,
  Network,
  Layers3,
  GitBranch,
  MessageSquare,
  Plus,
} from "lucide-react";
import { motion } from "framer-motion";
import { api } from "../services/api";
import type { Overview as Data, Node, Edge } from "../types";
import {
  PageHeading,
  SectionHeading,
  Loading,
  ErrorBox,
  Empty,
  Badge,
} from "../components/Common";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { GraphCanvas } from "../components/GraphCanvas";
export function Overview() {
  const q = useQuery({
    queryKey: ["overview"],
    queryFn: () => api<Data>("/analytics/overview"),
    refetchInterval: 10000,
  });
  const graph = useQuery({
    queryKey: ["graph-preview"],
    queryFn: () =>
      api<{ nodes: Node[]; edges: Edge[] }>("/graph/subgraph?limit=30"),
  });
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE / OVERVIEW"
        title="Connected knowledge. Clear answers."
        description="Turn your documents into an explorable network of evidence."
        action={
          <Button asChild>
            <Link to="/documents">
              <Plus size={16} /> Add documents
            </Link>
          </Button>
        }
      />
      <ErrorBox error={q.error} />
      {q.isPending ? (
        <Loading />
      ) : (
        q.data && (
          <>
            <div className="stats-grid">
              {[
                [FileText, "Documents", q.data.documents],
                [Layers3, "Indexed chunks", q.data.chunks],
                [Network, "Graph entities", q.data.entities],
                [GitBranch, "Relationships", q.data.relationships],
                [MessageSquare, "Queries", q.data.queries],
              ].map(([Icon, label, value], i) => {
                const I = Icon as typeof FileText;
                return (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    key={String(label)}
                  >
                    <Card className="stat">
                      <div>
                        <span>{String(label)}</span>
                        <I size={17} />
                      </div>
                      <strong>{Number(value).toLocaleString()}</strong>
                      <small>Live workspace data</small>
                    </Card>
                  </motion.div>
                );
              })}
            </div>
            <div className="overview-grid">
              <Card className="graph-preview">
                <SectionHeading
                  title="Your knowledge, connected"
                  link="Explore graph"
                  to="/graph"
                />
                {graph.data?.nodes.length ? (
                  <GraphCanvas {...graph.data} />
                ) : (
                  <Empty>
                    <Network size={36} />
                    <p>Your graph starts with a document.</p>
                    <Link to="/documents">
                      Upload the demonstration corpus <ArrowRight size={14} />
                    </Link>
                  </Empty>
                )}
                <div className="graph-legend">
                  <span>
                    <i className="dot violet" />
                    Person
                  </span>
                  <span>
                    <i className="dot lime" />
                    Organization
                  </span>
                  <span>
                    <i className="dot blue" />
                    Location
                  </span>
                  <Badge>Database facts</Badge>
                </div>
              </Card>
              <Card>
                <SectionHeading title="Recent activity" />
                {!q.data.recent_documents.length &&
                !q.data.recent_queries.length ? (
                  <Empty>No activity yet. Upload a document to begin.</Empty>
                ) : (
                  <div className="activity">
                    {q.data.recent_documents.map((d) => (
                      <div key={d.id}>
                        <span className="activity-icon">
                          <FileText size={16} />
                        </span>
                        <div>
                          <b>{d.name}</b>
                          <small>
                            {d.status} · {d.chunks} chunks
                          </small>
                        </div>
                        <span className={`status ${d.status}`}>
                          {d.progress}%
                        </span>
                      </div>
                    ))}
                    {q.data.recent_queries.slice(0, 3).map((r) => (
                      <div key={r.id}>
                        <span className="activity-icon">
                          <MessageSquare size={16} />
                        </span>
                        <div>
                          <b>{r.question}</b>
                          <small>
                            {r.strategy} · {r.latency_ms.toFixed(0)} ms
                          </small>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
            <Card className="callout">
              <div className="callout-icon">
                <GitBranch size={28} />
              </div>
              <div>
                <Badge>THE GRAPHRAG DIFFERENCE</Badge>
                <h2>Follow the connections that similarity search can miss.</h2>
                <p>
                  Compare vector retrieval with graph-supported evidence using
                  the same answer model.
                </p>
              </div>
              <Button asChild variant="outline">
                <Link to="/lab">
                  Open comparison lab <ArrowRight size={16} />
                </Link>
              </Button>
            </Card>
          </>
        )
      )}
    </>
  );
}
