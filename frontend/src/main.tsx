import React from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  NavLink,
  useLocation,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import {
  Network,
  LayoutDashboard,
  Files,
  MessageSquare,
  GitBranch,
  FlaskConical,
  BarChart3,
  Settings as SettingsIcon,
  ArrowUpRight,
} from "lucide-react";
const Overview = React.lazy(() =>
  import("./pages/Overview").then((m) => ({ default: m.Overview })),
);
const Documents = React.lazy(() =>
  import("./pages/Documents").then((m) => ({ default: m.Documents })),
);
const Ask = React.lazy(() =>
  import("./pages/Ask").then((m) => ({ default: m.Ask })),
);
const Graph = React.lazy(() =>
  import("./pages/Graph").then((m) => ({ default: m.Graph })),
);
const Lab = React.lazy(() =>
  import("./pages/Lab").then((m) => ({ default: m.Lab })),
);
const Analytics = React.lazy(() =>
  import("./pages/Analytics").then((m) => ({ default: m.Analytics })),
);
const Settings = React.lazy(() =>
  import("./pages/Settings").then((m) => ({ default: m.Settings })),
);
import type { OllamaStatus } from "./types";
import { api } from "./services/api";
import "./styles.css";
import { Loading } from "./components/Common";
const navigation = [
  ["/", "Overview", LayoutDashboard],
  ["/documents", "Documents", Files],
  ["/ask", "Ask GraphMind", MessageSquare],
  ["/graph", "Knowledge graph", GitBranch],
  ["/lab", "Comparison lab", FlaskConical],
  ["/analytics", "Analytics", BarChart3],
  ["/settings", "Settings", SettingsIcon],
] as const;
function App() {
  const location = useLocation();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ status: string; provider: string }>("/health"),
    refetchInterval: 30000,
    retry: false,
  });
  const ollama = useQuery({ queryKey: ["ollama"], queryFn: () => api<OllamaStatus>("/ollama/status"), refetchInterval: 15000, retry: false });
  return (
    <div className="app">
      <aside className="sidebar">
        <NavLink to="/" className="brand">
          <span className="brand-symbol">
            <Network size={24} />
          </span>
          graphmind<span className="brand-period">.</span>
        </NavLink>
        <div className="workspace">
          <span className="workspace-avatar">G</span>
          <div>
            Research workspace<small>LOCAL DEVELOPMENT</small>
          </div>
          <span className="workspace-dot" />
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav>
          {navigation.map(([path, label, Icon], i) => (
            <React.Fragment key={path}>
              {i === 4 && (
                <span className="nav-label secondary-label">
                  RESEARCH & EVALUATION
                </span>
              )}
              <NavLink to={path} end={path === "/"}>
                <Icon size={18} />
                {label}
                {path === "/ask" && <span className="nav-new">AI</span>}
              </NavLink>
            </React.Fragment>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div>
            <i className={`dot ${health.isSuccess ? "lime" : "amber"}`} />
            {health.isSuccess ? "Engine connected" : "Engine needs attention"}
          </div>
          <small>{ollama.data?.ready ? `Ollama · ${ollama.data.answer_model}` : ollama.data?.connected ? "Ollama: model setup required" : "Ollama unavailable"}</small>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            API documentation <ArrowUpRight size={13} />
          </a>
        </div>
      </aside>
      <div className="main-shell">
        <header>
          <div className="breadcrumb">
            Workspace <span>/</span>{" "}
            <b>
              {navigation.find((n) => n[0] === location.pathname)?.[1] ??
                "Not found"}
            </b>
          </div>
          <div className="header-right">
            <span className="environment-tag">
              <i className="dot lime" /> LOCAL ENVIRONMENT
            </span>
            <span className="avatar">GM</span>
          </div>
        </header>
        <main>
          <React.Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/ask" element={<Ask />} />
              <Route path="/graph" element={<Graph />} />
              <Route path="/lab" element={<Lab />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<h1>Page not found</h1>} />
            </Routes>
          </React.Suspense>
          <footer>
            GRAPHMIND <span>Connected intelligence, backed by evidence.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
class Boundary extends React.Component<
  { children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="empty">
        <h1>Something went wrong.</h1>
        <button onClick={() => window.location.reload()}>
          Reload workspace
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
const client = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 5000 } },
});
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Boundary>
      <QueryClientProvider client={client}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </Boundary>
  </React.StrictMode>,
);
