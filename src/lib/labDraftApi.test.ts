import { afterEach, describe, expect, it, vi } from "vitest";

import {
  correctLabObservation,
  labDraftStatusLabel,
  type LabDraftFields,
  type LabDraftStatus,
  type LabObservation,
  type LabValueKind,
} from "./labDraftApi";

const fields: LabDraftFields = {
  source_analyte_text: "Глюкоза",
  source_value_text: "5.6",
  value_kind: "numeric",
  numeric_value: "5.6",
  source_unit_text: "ммоль/л",
  unit_not_present: false,
  source_reference_range_text: "3.9–6.1",
  reference_range_not_present: false,
  source_observed_at_text: "13.07.2026",
  observed_time_unknown: false,
  observed_date: "2026-07-13",
  observed_precision: "date",
};

function observation(
  patientDecision: "match" | "not_present" = "match",
): LabObservation {
  return {
    ...fields,
    id: "11111111-1111-4111-8111-111111111111",
    profile_id: "22222222-2222-4222-8222-222222222222",
    document_id: "33333333-3333-4333-8333-333333333333",
    ocr_run_id: "44444444-4444-4444-8444-444444444444",
    patient_decision_id: "55555555-5555-4555-8555-555555555555",
    source_draft_id: "66666666-6666-4666-8666-666666666666",
    status: "active",
    patient_decision: patientDecision,
    sources: [],
    source_draft_updated_at: "2026-07-13T10:00:00Z",
    source_document_updated_at: "2026-07-13T10:00:00Z",
    source_review_finalized_at: "2026-07-13T10:00:00Z",
    source_patient_decision_updated_at: "2026-07-13T10:00:00Z",
    confirmed_by_user_id: "77777777-7777-4777-8777-777777777777",
    confirmed_at: "2026-07-13T10:00:00Z",
    created_at: "2026-07-13T10:00:00Z",
    lifecycle_version: 1,
    lifecycle_updated_at: "2026-07-13T10:00:00Z",
  };
}

function successfulFetch() {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(observation()), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function requestBody(fetchMock: ReturnType<typeof successfulFetch>): Record<string, unknown> {
  const firstCall = fetchMock.mock.calls.at(0);
  if (!firstCall) throw new Error("Expected one fetch call");
  const init = firstCall[1] as RequestInit | undefined;
  return JSON.parse(String(init?.body)) as Record<string, unknown>;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Lab draft helpers", () => {
  it("has an explicit label for every draft lifecycle state", () => {
    const statuses: LabDraftStatus[] = [
      "draft",
      "ready",
      "rejected",
      "confirmed",
    ];
    const labels = statuses.map((status) => labDraftStatusLabel(status));
    expect(new Set(labels).size).toBe(statuses.length);
    expect(labDraftStatusLabel("draft")).toBe("Черновик");
    expect(labDraftStatusLabel("ready")).toContain("отдельному подтверждению");
    expect(labDraftStatusLabel("rejected")).toBe("Исключено");
    expect(labDraftStatusLabel("confirmed")).toBe("Подтверждено");
  });

  it("keeps value kinds explicit and separate", () => {
    const kinds: LabValueKind[] = ["numeric", "text", "qualitative"];
    expect(kinds).toEqual(["numeric", "text", "qualitative"]);
  });
});

describe("correctLabObservation acknowledgement boundary", () => {
  it("does not send a request when the base acknowledgement is cancelled", async () => {
    const fetchMock = successfulFetch();
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    await expect(
      correctLabObservation(
        "22222222-2222-4222-8222-222222222222",
        observation(),
        "Исправлена опечатка",
        fields,
        "correct:0123456789abcdef",
      ),
    ).rejects.toMatchObject({ status: 422 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends every fresh acknowledgement for a matched patient", async () => {
    const fetchMock = successfulFetch();
    vi.stubGlobal("fetch", fetchMock);
    const confirmMock = vi.spyOn(window, "confirm").mockReturnValue(true);

    await correctLabObservation(
      "22222222-2222-4222-8222-222222222222",
      observation("match"),
      "Исправлена опечатка",
      fields,
      "correct:0123456789abcdef",
    );

    expect(confirmMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const firstCall = fetchMock.mock.calls.at(0);
    expect(String(firstCall?.[0])).toContain("/correct");
    expect(requestBody(fetchMock)).toMatchObject({
      acknowledge_source_matches: true,
      acknowledge_unit_and_range: true,
      acknowledge_observed_at: true,
      acknowledge_profile: true,
      acknowledge_structured_record: true,
      acknowledge_not_present_assignment: false,
    });
  });

  it("requires a second assignment acknowledgement for not_present", async () => {
    const fetchMock = successfulFetch();
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm")
      .mockReturnValueOnce(true)
      .mockReturnValueOnce(false);

    await expect(
      correctLabObservation(
        "22222222-2222-4222-8222-222222222222",
        observation("not_present"),
        "Исправлена опечатка",
        fields,
        "correct:0123456789abcdef",
      ),
    ).rejects.toMatchObject({ status: 422 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the not_present assignment acknowledgement only after approval", async () => {
    const fetchMock = successfulFetch();
    vi.stubGlobal("fetch", fetchMock);
    const confirmMock = vi.spyOn(window, "confirm").mockReturnValue(true);

    await correctLabObservation(
      "22222222-2222-4222-8222-222222222222",
      observation("not_present"),
      "Исправлена опечатка",
      fields,
      "correct:0123456789abcdef",
    );

    expect(confirmMock).toHaveBeenCalledTimes(2);
    expect(requestBody(fetchMock).acknowledge_not_present_assignment).toBe(true);
  });
});
