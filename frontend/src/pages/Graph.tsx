import { useState, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Network, ChevronLeft, ChevronRight } from "lucide-react";
import { useLocation } from "react-router-dom";
import { api } from "../services/api";
import type { Node, Edge, Document, Path } from "../types";
import {
  PageHeading,
  ErrorBox,
  Empty,
  Badge,
  Loading,
} from "../components/Common";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { GraphCanvas } from "../components/GraphCanvas";
export function Graph() {
  const [search, setSearch] = useState("");
  const [doc, setDoc] = useState("");
  const [type, setType] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Node | Edge | null>(null);
  const location = useLocation();
  const highlighted = (location.state as { paths?: Path[] } | null)?.paths;
  const q = useQuery({
    queryKey: ["graph", search, doc, type, offset],
    queryFn: () =>
      api<{ nodes: Node[]; edges: Edge[] }>(
        "/graph/subgraph?" +
          new URLSearchParams({
            search,
            document_id: doc,
            type,
            offset: String(offset),
          })
            .toString()
            .replace("document_id=&", "")
            .replace("type=&", ""),
      ),
  });
  const docs = useQuery({
    queryKey: ["documents"],
    queryFn: () => api<Document[]>("/documents"),
  });
  const choose = useCallback((n: Node | Edge) => setSelected(n), []);
  const nodes = useMemo(
    () =>
      highlighted
        ? [
            ...new Map(
              highlighted.flatMap((p) => p.nodes).map((n) => [n.id, n]),
            ).values(),
          ]
        : q.data?.nodes,
    [highlighted, q.data],
  );
  const edges = useMemo(
    () =>
      highlighted
        ? [
            ...new Map(
              highlighted.flatMap((p) => p.edges).map((e) => [e.id, e]),
            ).values(),
          ]
        : q.data?.edges,
    [highlighted, q.data],
  );
  const highlightIds = useMemo(
    () => (highlighted ? (edges?.map((e) => e.id) ?? []) : []),
    [highlighted, edges],
  );
  return (
    <>
      <PageHeading
        eyebrow="RESEARCH / KNOWLEDGE GRAPH"
        title="Explore the connections."
        description="Inspect database relationships and the exact document evidence behind them."
        action={<Badge>Bounded subgraph · 60 nodes / 300 edges</Badge>}
      />
      <div className="toolbar">
        <label className="search">
          <Search size={16} />
          <input
            aria-label="Search entities"
            placeholder="Search entities…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <select
          aria-label="Filter by entity type"
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All entity types</option>
          {[
            "Person",
            "Organization",
            "Company",
            "Location",
            "Technology",
            "Product",
            "Event",
            "Date",
          ].map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <select
          aria-label="Filter by document"
          value={doc}
          onChange={(e) => {
            setDoc(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All documents</option>
          {docs.data?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <Button
          variant="outline"
          aria-label="Previous graph page"
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 60))}
        >
          <ChevronLeft size={16} />
        </Button>
        <Button
          variant="outline"
          aria-label="Next graph page"
          disabled={(q.data?.nodes.length ?? 0) < 60}
          onClick={() => setOffset(offset + 60)}
        >
          <ChevronRight size={16} />
        </Button>
      </div>
      <ErrorBox error={q.error} />
      <div className="explorer-layout">
        <Card className="graph-full">
          {q.isPending ? (
            <Loading />
          ) : nodes?.length ? (
            <GraphCanvas
              nodes={nodes}
              edges={edges ?? []}
              onSelect={choose}
              highlight={highlightIds}
            />
          ) : (
            <Empty>
              <Network size={36} />
              <p>No entities match. Upload documents or adjust filters.</p>
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
            <span>Scroll to zoom · drag to pan</span>
          </div>
        </Card>
        <Card className="inspector">
          <h2>Evidence inspector</h2>
          <select
            aria-label="Inspect entity"
            value={selected && "name" in selected ? selected.id : ""}
            onChange={(e) =>
              setSelected(nodes?.find((n) => n.id === e.target.value) ?? null)
            }
          >
            <option value="">Select an entity…</option>
            {nodes?.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Inspect relationship"
            value={selected && "evidence" in selected ? selected.id : ""}
            onChange={(e) =>
              setSelected(edges?.find((n) => n.id === e.target.value) ?? null)
            }
          >
            <option value="">Select a relationship…</option>
            {edges?.map((n) => (
              <option key={n.id} value={n.id}>
                {nodes?.find((v) => v.id === n.source)?.name} → {n.type} →{" "}
                {nodes?.find((v) => v.id === n.target)?.name}
              </option>
            ))}
          </select>
          {selected ? (
            <>
              <Badge>{selected.type}</Badge>
              {"name" in selected ? (
                <>
                  <h2>{selected.name}</h2>
                  <code>{selected.id}</code>
                  <p className="muted">
                    Aliases: {selected.aliases?.join(", ") || "None recorded"}
                  </p>
                </>
              ) : (
                <>
                  <h3>{selected.type.replaceAll("_", " ")}</h3>
                  <p className="muted small">
                    Directed: {selected.source.slice(0, 10)} →{" "}
                    {selected.target.slice(0, 10)}
                  </p>
                  <blockquote>{selected.evidence}</blockquote>
                  <p>Extraction confidence: {selected.confidence}</p>
                  <a href={`/api/documents/${selected.document_id}/source`}>
                    Download source document ↗
                  </a>
                  <p className="muted small">Chunk: {selected.chunk_id}</p>
                </>
              )}
            </>
          ) : (
            <Empty>
              Select a node or relationship to inspect its source provenance.
            </Empty>
          )}
        </Card>
      </div>
    </>
  );
}
