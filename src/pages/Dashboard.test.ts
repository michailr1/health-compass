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

const completion = {
  completed_sections: 1,
  total_sections: 5,
  progress_percent: 20,
  next_section: "conditions",
  sections: [
    {
      key: "conditions",
      title: "Состояния и симптомы",
      state: "incomplete",
      missing_fields: ["review_required"],
      next_action: "#clinical-conditions",
    },
  ],
};

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("loadDashboard", () => {
  it("loads profile completion even when the dashboard snapshot is missing", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([profile]))
      .mockResolvedValueOnce(jsonResponse(completion))
      .mockResolvedValueOnce(jsonResponse({ detail: "Dashboard not found" }, 404));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadDashboard()).resolves.toEqual({
      profile,
      dashboard: null,
      completion,
    });
  });

  it("keeps the dashboard usable when only completion loading fails", async () => {
    const dashboard = {
      id: "44444444-4444-4444-4444-444444444444",
      profile_id: profile.id,
      summary: {
        observationIndex: 80,
        avgSleep: { hours: 7, minutes: 20 },
        shortNightsPct: 10,
        activeDays: 20,
        geneticPositions: 0,
      },
      priorities: [],
      source_label: "test",
      created_at: "2026-07-10T00:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([profile]))
      .mockResolvedValueOnce(jsonResponse({ detail: "Completion unavailable" }, 503))
      .mockResolvedValueOnce(jsonResponse(dashboard));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadDashboard()).resolves.toEqual({
      profile,
      dashboard,
      completion: null,
    });
  });

  it("still propagates unexpected dashboard API failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([profile]))
      .mockResolvedValueOnce(jsonResponse(completion))
      .mockResolvedValueOnce(jsonResponse({ detail: "Database unavailable" }, 503));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadDashboard()).rejects.toThrow("Database unavailable");
  });
});
