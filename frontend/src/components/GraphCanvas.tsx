import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import type { Node, Edge } from "../types";
import { Plus, Minus, Maximize } from "lucide-react";
const EMPTY_IDS: string[] = [];
export function GraphCanvas({
  nodes,
  edges,
  onSelect,
  highlight = EMPTY_IDS,
}: {
  nodes: Node[];
  edges: Edge[];
  onSelect?: (item: Node | Edge) => void;
  highlight?: string[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const instance = useRef<cytoscape.Core | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    const cy = cytoscape({
      container: ref.current,
      elements: [
        ...nodes.map((n) => ({ data: { ...n, label: n.name } })),
        ...edges.map((e) => ({
          data: { ...e, label: e.type.replaceAll("_", " ") },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#a3e635",
            label: "data(label)",
            color: "#dce6f2",
            "font-size": 11,
            "text-valign": "bottom",
            "text-margin-y": 10,
            width: 22,
            height: 22,
            "border-width": 5,
            "border-color": "#283d28",
          },
        },
        {
          selector: 'node[type="Person"]',
          style: { "background-color": "#a78bfa", "border-color": "#382e54" },
        },
        {
          selector: 'node[type="Location"]',
          style: { "background-color": "#38bdf8", "border-color": "#1e4055" },
        },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": "#48536b",
            "target-arrow-color": "#6c7e9c",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "#8a98ae",
            "text-rotation": "autorotate",
            "text-margin-y": -9,
          },
        },
        {
          selector: ":selected",
          style: {
            "background-color": "#fff",
            "line-color": "#a3e635",
            "target-arrow-color": "#a3e635",
          },
        },
      ],
      layout:
        nodes.length <= 12
          ? {
              name: "breadthfirst",
              directed: true,
              spacingFactor: 1.25,
              padding: 50,
              animate: false,
            }
          : {
              name: "cose",
              animate: false,
              padding: 60,
              nodeDimensionsIncludeLabels: true,
              nodeRepulsion: () => 100000,
              idealEdgeLength: () => 140,
            },
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.25,
    });
    instance.current = cy;
    cy.on("tap", "node,edge", (event) => onSelect?.(event.target.data()));
    highlight.forEach((id) => cy.getElementById(id).select());
    const observer = new ResizeObserver(() => cy.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      instance.current = null;
      cy.destroy();
    };
  }, [nodes, edges, onSelect, highlight]);
  return (
    <div className="graph-surface">
      <div
        className="graph-canvas"
        ref={ref}
        role="img"
        aria-label={`Knowledge graph with ${nodes.length} entities and ${edges.length} relationships`}
      />
      <div className="graph-controls">
        <button
          aria-label="Zoom graph in"
          onClick={() => {
            const c = instance.current;
            if (c) c.zoom(c.zoom() * 1.25);
          }}
        >
          <Plus size={14} />
        </button>
        <button
          aria-label="Zoom graph out"
          onClick={() => {
            const c = instance.current;
            if (c) c.zoom(c.zoom() / 1.25);
          }}
        >
          <Minus size={14} />
        </button>
        <button
          aria-label="Fit graph"
          onClick={() => instance.current?.fit(undefined, 40)}
        >
          <Maximize size={14} />
        </button>
      </div>
    </div>
  );
}
