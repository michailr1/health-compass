import { describe, expect, it } from "vitest";

import {
  labDraftStatusLabel,
  type LabDraftStatus,
  type LabValueKind,
} from "./labDraftApi";

describe("Lab draft helpers", () => {
  it("has an explicit label for every non-clinical draft state", () => {
    const statuses: LabDraftStatus[] = ["draft", "ready", "rejected"];
    const labels = statuses.map((status) => labDraftStatusLabel(status));
    expect(new Set(labels).size).toBe(statuses.length);
    expect(labDraftStatusLabel("draft")).toBe("Черновик");
    expect(labDraftStatusLabel("ready")).toContain("отдельному подтверждению");
    expect(labDraftStatusLabel("rejected")).toBe("Исключено");
  });

  it("keeps value kinds explicit and separate", () => {
    const kinds: LabValueKind[] = ["numeric", "text", "qualitative"];
    expect(kinds).toEqual(["numeric", "text", "qualitative"]);
  });
});
