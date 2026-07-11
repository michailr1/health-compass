import { describe, expect, it } from "vitest";

import {
  buildPermanentErasurePayload,
  isPermanentErasureOwner,
} from "./ClinicalRecordActions";

describe("clinical record permanent erasure", () => {
  it("shows the permanent action only to the profile owner", () => {
    expect(isPermanentErasureOwner("owner-1", "owner-1")).toBe(true);
    expect(isPermanentErasureOwner("editor-1", "owner-1")).toBe(false);
    expect(isPermanentErasureOwner(null, "owner-1")).toBe(false);
  });

  it("always sends explicit confirmation and optimistic concurrency", () => {
    expect(buildPermanentErasurePayload({ updated_at: "2026-07-11T18:00:00Z" })).toEqual({
      expected_updated_at: "2026-07-11T18:00:00Z",
      confirm_permanent_deletion: true,
    });
  });
});
