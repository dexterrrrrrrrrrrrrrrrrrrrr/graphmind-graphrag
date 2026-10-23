export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers:
      options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.error?.message ?? `Request failed (${response.status})`,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export const post = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const metric = (value: number | null | undefined, suffix = "") =>
  value == null
    ? "—"
    : `${Number.isInteger(value) ? value : value.toFixed(1)}${suffix}`;


export async function streamQuestion<T>(body: unknown, onProgress: (message: string) => void): Promise<T> {
  const response = await fetch("/api/query/stream", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.error?.message ?? `Request failed (${response.status})`);
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Streaming is unavailable in this browser");
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const {done, value} = await reader.read();
      buffer += decoder.decode(value, {stream: !done});
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (!frame.startsWith("data: ")) continue;
        const event = JSON.parse(frame.slice(6));
        if (event.event === "error") throw new Error(event.data.message);
        if (event.event === "answer") return event.data as T;
        onProgress(event.event === "loading" ? `Loading local model ${event.data.model}…` : event.event === "generating" ? `Generating locally with ${event.data.model}…` : "Retrieving source evidence…");
      }
      if (done) throw new Error("Inference stream ended before a validated answer arrived");
    }
  } finally { await reader.cancel(); }
}
