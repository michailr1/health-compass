import { describe, expect, it } from "vitest";

import { severityLabel } from "./ClinicalContextSection";


describe("severityLabel", () => {
  it("returns a clear Russian label for severe allergies", () => {
    expect(severityLabel("severe")).toBe("тяжёлая");
  });

  it("keeps unknown severity explicit", () => {
    expect(severityLabel("unknown")).toBe("тяжесть неизвестна");
  });
});
