import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { api, metric } from "../services/api";
import { PageHeading, ErrorBox, Empty } from "../components/Common";
import { Card } from "../components/ui/card";
type Latency = {
  window: number;
  average_ms: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
  samples: { id: string; strategy: string; latency_ms: number }[];
  token_usage: { input_tokens: number; output_tokens: number };
  usage_measured_queries: number;
};
type Retrieval = {
  distribution: {
    strategy: string;
    count: number;
    average_latency_ms: number;
  }[];
  average_evidence_count: number | null;
  empty_retrievals: number;
  window: number;
  evaluation: Record<string, Record<string, number | null>>;
};
export function Analytics() {
  const latency = useQuery({
    queryKey: ["latency"],
    queryFn: () => api<Latency>("/analytics/latency"),
  });
  const retrieval = useQuery({
    queryKey: ["retrieval"],
    queryFn: () => api<Retrieval>("/analytics/retrieval"),
  });
  return (
    <>
      <PageHeading
        eyebrow="EVALUATION / ANALYTICS"
        title="Observe. Measure. Improve."
        description="Real query telemetry and reproducible evaluation results. No synthetic dashboard metrics."
      />
      <ErrorBox error={latency.error ?? retrieval.error} />
      <div className="stats-grid four">
        {[
          ["Average latency", metric(latency.data?.average_ms, " ms")],
          ["Median / P50", metric(latency.data?.p50_ms, " ms")],
          ["Tail / P95", metric(latency.data?.p95_ms, " ms")],
          [
            "Avg. evidence chunks",
            metric(retrieval.data?.average_evidence_count),
          ],
        ].map(([label, value]) => (
          <Card className="stat" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>
              Most recent {latency.data?.window ?? 0} queries (max 1,000)
            </small>
          </Card>
        ))}
      </div>
      <div className="comparison-grid">
        <Card>
          <h2>Query latency</h2>
          {latency.data?.samples.length ? (
            <ResponsiveContainer width="100%" height={290}>
              <BarChart data={[...latency.data.samples].reverse()}>
                <CartesianGrid stroke="#242c3b" vertical={false} />
                <XAxis
                  dataKey="strategy"
                  tick={{ fill: "#8b98ac", fontSize: 11 }}
                />
                <YAxis tick={{ fill: "#8b98ac", fontSize: 11 }} unit="ms" />
                <Tooltip
                  contentStyle={{
                    background: "#161d29",
                    border: "1px solid #303a4b",
                  }}
                />
                <Bar
                  dataKey="latency_ms"
                  fill="#a3e635"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty>Run a query to collect latency samples.</Empty>
          )}
        </Card>
        <Card>
          <h2>Retrieval mode distribution</h2>
          {retrieval.data?.distribution.length ? (
            <ResponsiveContainer width="100%" height={290}>
              <PieChart>
                <Pie
                  data={retrieval.data.distribution}
                  dataKey="count"
                  nameKey="strategy"
                  innerRadius={65}
                  outerRadius={100}
                  label
                >
                  {retrieval.data.distribution.map((d, i) => (
                    <Cell
                      key={d.strategy}
                      fill={["#a3e635", "#a78bfa", "#38bdf8"][i % 3]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "#161d29",
                    border: "1px solid #303a4b",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <Empty>Mode distribution appears after your first query.</Empty>
          )}
        </Card>
      </div>
      <Card>
        <h2>Usage & evidence</h2>
        <div className="metrics-line">
          <span>
            Measured input tokens{" "}
            <b>
              {latency.data?.usage_measured_queries
                ? latency.data.token_usage.input_tokens
                : "Unavailable"}
            </b>
          </span>
          <span>
            Measured output tokens{" "}
            <b>
              {latency.data?.usage_measured_queries
                ? latency.data.token_usage.output_tokens
                : "Unavailable"}
            </b>
          </span>
          <span>
            Empty retrievals <b>{retrieval.data?.empty_retrievals ?? 0}</b>
          </span>
        </div>
        <p className="muted small">
          Token totals cover {latency.data?.usage_measured_queries ?? 0}{" "}
          provider-reported queries in the current window. Queries without inference
          have no token accounting.
        </p>
      </Card>
      <Card>
        <h2>Benchmark aggregates</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Mode</th>
                <th>Executed / failed</th>
                <th>Answer accuracy</th>
                <th>Multi-hop accuracy</th>
                <th>Evidence recall</th>
                <th>Citation correctness</th>
                <th>Path correctness</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(retrieval.data?.evaluation ?? {}).map(
                ([mode, m]) => (
                  <tr key={mode}>
                    <td>{mode}</td>
                    <td>
                      {m.executed} / {m.failed}
                    </td>
                    {[
                      "answer_accuracy",
                      "multi_hop_accuracy",
                      "evidence_recall",
                      "citation_correctness",
                      "graph_path_correctness",
                    ].map((k) => (
                      <td key={k}>{metric(m[k])}</td>
                    ))}
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          Null metrics mean no applicable observations. Results include the
          provider and settings used; compare runs with matching configurations.
        </p>
      </Card>
    </>
  );
}
