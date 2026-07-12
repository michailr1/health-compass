import { describe, expect, it } from "vitest";

import {
  candidateStatusLabel,
  patientDecisionLabel,
  type OCRCandidateStatus,
  type OCRPatientDecision,
} from "./documentOcrReviewApi";

describe("OCR human review helpers", () => {
  it("has a safe label for every candidate state", () => {
    const statuses: OCRCandidateStatus[] = [
      "needs_review",
      "accepted",
      "edited",
      "rejected",
      "deferred",
    ];
    for (const status of statuses) {
      expect(candidateStatusLabel(status)).not.toBe("");
    }
    expect(candidateStatusLabel("accepted")).toBe("Принято без изменений");
    expect(candidateStatusLabel("deferred")).toBe("Отложено");
  });

  it("uses explicit patient-decision wording", () => {
    const decisions: OCRPatientDecision[] = [
      "unknown",
      "match",
      "mismatch",
      "not_present",
    ];
    for (const decision of decisions) {
      expect(patientDecisionLabel(decision)).not.toBe("");
    }
    expect(patientDecisionLabel("match")).toContain("этому профилю");
    expect(patientDecisionLabel("mismatch")).toContain("другому человеку");
    expect(patientDecisionLabel("unknown")).not.toContain("совпадает");
  });
});
