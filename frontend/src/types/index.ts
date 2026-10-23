export type Mode = "auto" | "vector" | "graph" | "hybrid";
export const modes: Record<Mode, string> = {
  auto: "Auto route",
  vector: "Standard RAG",
  graph: "Graph retrieval",
  hybrid: "Hybrid GraphRAG",
};
export interface Document {
  processing_metadata?: {
    extraction_diagnostics?: { rejected_relationship_count: number };
  };
  id: string;
  name: string;
  status: string;
  progress: number;
  size: number;
  chunks: number;
  error: string | null;
  created_at: string;
}
export interface Node {
  id: string;
  name: string;
  type: string;
  aliases?: string[];
}
export interface Edge {
  id: string;
  source: string;
  target: string;
  type: string;
  evidence: string;
  document_id: string;
  chunk_id: string;
  confidence: number;
}
export interface Path {
  nodes: Node[];
  edges: Edge[];
  score: number;
}
export interface Evidence {
  chunk_id: string;
  document_id: string;
  document_name: string;
  text: string;
  page: number | null;
  score: number;
  sources: string[];
}
export interface Answer {
  id: string;
  question: string;
  answer: string;
  strategy: Mode;
  requested_mode: Mode;
  routing_reason: string;
  fallback: string | null;
  evidence: Evidence[];
  citations: Evidence[];
  paths: Path[];
  latency_ms: number;
  retrieval_ms: number;
  token_usage: { input_tokens: number; output_tokens: number } | null;
  estimated_cost_usd: number | null;
  provider: string;
  model: string;
  warnings: string[];
}
export interface Overview {
  documents: number;
  chunks: number;
  entities: number;
  relationships: number;
  queries: number;
  recent_queries: Answer[];
  recent_documents: Document[];
  ingestion: Record<string, number>;
  retrieval: { strategy: Mode; count: number; average_latency_ms: number }[];
}
export interface Settings {
  llm_provider: string;
  llm_model: string;
  top_k: number;
  max_depth: number;
  similarity_threshold: number;
  chunk_size: number;
  chunk_overlap: number;
  context_tokens: number;
  reranking: boolean;
  fusion: string;
  vector_weight: number;
  default_mode: Mode;
  embedding_model: string;
  extraction_model: string;
  ollama_context_length: number;
  request_timeout: number;
  notice: string;
}
export interface BenchmarkRow {
  question_id: string;
  question: string;
  mode: "vector" | "hybrid";
  required_hops: number;
  status: string;
  error?: string;
  response?: Answer;
  metrics: Record<string, number | null> | null;
}
export interface Benchmark {
  id: string;
  created_at: string;
  dataset_version: string;
  provider: string;
  model: string;
  rows: BenchmarkRow[];
}

export interface OllamaStatus {
  connected: boolean;
  ready: boolean;
  answer_model: string;
  extraction_model: string;
  models: { name: string; size: number }[];
  loaded_models: { name: string }[];
  missing_models: string[];
  message: string;
}
