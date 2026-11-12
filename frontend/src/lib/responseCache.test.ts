import { describe, it, expect, vi } from "vitest";
import { responseCache } from "./responseCache";

describe("terrain response reuse", () => {
  it("shares concurrent requests and reuses them when returning to a site", async () => {
    const cached = responseCache<number>();
    const load = vi.fn(async () => 42);
    const first = cached("point-A", load);
    expect(cached("point-A", load)).toBe(first);
    await first;
    await cached("point-B", load);
    expect(await cached("point-A", load)).toBe(42);
    expect(load).toHaveBeenCalledTimes(2);
  });
  it("retries failures and expires old data after the freshness interval", async () => {
    vi.useFakeTimers();
    try {
      const cached = responseCache<number>(2, 1000);
      await expect(cached("point", async () => { throw new Error("offline"); })).rejects.toThrow("offline");
      expect(await cached("point", async () => 1)).toBe(1);
      vi.advanceTimersByTime(1001);
      expect(await cached("point", async () => 2)).toBe(2);
    } finally { vi.useRealTimers(); }
  });
});
