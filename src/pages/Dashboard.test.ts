import { afterEach, describe, expect, it, vi } from "vitest";

import { loadDashboard } from "./Dashboard";

const profile = {
  id: "11111111-1111-1111-1111-111111111111",
  workspace_id: "22222222-2222-2222-2222-222222222222",
  owner_user_id: "33333333-3333-3333-3333-333333333333",
  display_name: "Новый профиль",
  date_of_birth: null,
  sex: null,
  height_cm: null,
  timezone: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("loadDashboard", () => {
  it("treats a missing snapshot as a valid empty dashboard", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([profile]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Dashboard not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadDashboard()).resolves.toEqual({
      profile,
      dashboard: null,
    });
  });

  it("still propagates unexpected API failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([profile]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Database unavailable" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadDashboard()).rejects.toThrow("Database unavailable");
  });
});
