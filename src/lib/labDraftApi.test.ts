import { describe, expect, it } from "vitest";

import {
  labDraftStatusLabel,
  type LabDraftStatus,
  type LabValueKind,
} from "./labDraftApi";

describe("Lab draft helpers", () => {
  it("has an explicit label for every non-clinical draft state", () => {
    const statuses: LabDraftStatus[] = ["draft", "ready", "rejected"];
    for (const status of statuses) {
      expect(labDraftStatusLabel(status)).not.toBe("");
    }
    expect(labDraftStatusLabel("draft")).toBe("Черновик");
    expect(labDraftStatusLabel("ready")).toContain("отдельному подтверждению");
  });

  it("keeps value kinds explicit and separate", () => {
    const kinds: LabValueKind[] = ["numeric", "text", "qualitative"];
    expect(kinds).toEqual(["numeric", "text", "qualitative"]);
  });
});
