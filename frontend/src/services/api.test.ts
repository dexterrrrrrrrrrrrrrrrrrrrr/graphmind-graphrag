import { afterEach, expect, it, vi } from "vitest";
import { api, metric } from "./api";
afterEach(() => vi.unstubAllGlobals());
it("preserves null measured metrics", () => {
  expect(metric(null)).toBe("—");
  expect(metric(0, " ms")).toBe("0 ms");
});
it("surfaces backend errors instead of inventing data", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ error: { message: "Neo4j unavailable" } }),
          { status: 503 },
        ),
      ),
  );
  await expect(api("/graph/stats")).rejects.toThrow("Neo4j unavailable");
});
it("supports deletion with no content", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
  );
  await expect(
    api("/documents/id", { method: "DELETE" }),
  ).resolves.toBeUndefined();
});

it("accepts only the final answer from fragmented inference events", async () => {
  const { streamQuestion } = await import("./api");
  const encoder = new TextEncoder();
  const wire = ': keepalive\n\ndata: {"event":"loading","data":{"model":"fixture"}}\n\ndata: {"event":"answer","data":{"answer":"validated fixture"}}\n\n';
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(new ReadableStream({
    start(controller) {
      for (let i = 0; i < wire.length; i += 7) controller.enqueue(encoder.encode(wire.slice(i, i + 7)));
      controller.close();
    },
  }))));
  const progress = vi.fn();
  await expect(streamQuestion({}, progress)).resolves.toEqual({answer: "validated fixture"});
  expect(progress).toHaveBeenCalledWith("Loading local model fixture…");
});

it("rejects interrupted streams without displaying a draft answer", async () => {
  const { streamQuestion } = await import("./api");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('data: {"event":"generating","data":{"model":"fixture"}}\n\n')));
  await expect(streamQuestion({}, vi.fn())).rejects.toThrow("before a validated answer");
});
