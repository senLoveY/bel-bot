import { beforeEach, describe, expect, it, vi } from "vitest";

// api.js читает Telegram и ?dev= при загрузке модуля, поэтому каждый тест грузит его заново
async function loadApi({ telegram, search = "" } = {}) {
  vi.resetModules();
  if (telegram) window.Telegram = { WebApp: telegram };
  window.history.replaceState({}, "", `/${search}`);
  return (await import("./api.js")).api;
}

function mockFetch(body = { ok: 1 }, status = 200) {
  global.fetch = vi.fn(async () => ({ ok: status < 400, status, json: async () => body }));
  return global.fetch;
}

describe("api client", () => {
  beforeEach(() => {
    mockFetch();
  });

  it("sends Telegram init data when running inside the Mini App", async () => {
    const api = await loadApi({ telegram: { initData: "auth=1" } });
    await api.me();
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toBe("/api/me");
    expect(opts.headers["X-Telegram-Init-Data"]).toBe("auth=1");
  });

  it("sends the dev user header in the browser when ?dev= is set", async () => {
    const api = await loadApi({ search: "?dev=5" });
    await api.today();
    const [, opts] = fetch.mock.calls[0];
    expect(opts.headers["X-Dev-User"]).toBe("5");
    expect(opts.headers["X-Telegram-Init-Data"]).toBeUndefined();
  });

  it("sends JSON bodies for updates", async () => {
    const api = await loadApi({ telegram: { initData: "x" } });
    await api.save(7, "learned");
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toBe("/api/cards/7/save");
    expect(opts.method).toBe("PUT");
    expect(JSON.parse(opts.body)).toEqual({ status: "learned" });
  });

  it("encodes admin search and revision status in the query", async () => {
    const api = await loadApi({ telegram: { initData: "x" } });
    await api.admin.revisions("rejected");
    await api.admin.users("Аля");
    expect(fetch.mock.calls[0][0]).toBe("/api/admin/revisions?status=rejected");
    expect(fetch.mock.calls[1][0]).toBe(`/api/admin/users?q=${encodeURIComponent("Аля")}`);
  });

  it("throws with the HTTP status on errors", async () => {
    mockFetch({}, 403);
    const api = await loadApi({ telegram: { initData: "x" } });
    await expect(api.admin.stats()).rejects.toThrow("403");
  });
});
