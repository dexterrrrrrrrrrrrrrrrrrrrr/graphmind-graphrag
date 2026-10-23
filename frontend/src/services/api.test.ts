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
