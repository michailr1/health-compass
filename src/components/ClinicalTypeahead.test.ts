import { describe, expect, it } from "vitest";

import { clinicalSuggestionsQueryKey, TYPEAHEAD_DEBOUNCE_MS } from "./ClinicalTypeahead";

describe("typeahead staleness protection (HC-015 Slice F / CR-15)", () => {
  it("keys suggestion caches by the exact query string", () => {
    const older = clinicalSuggestionsQueryKey("p1", "conditions", "миг");
    const newer = clinicalSuggestionsQueryKey("p1", "conditions", "мигрень");
    // Distinct cache entries mean an out-of-order response for «миг» can
    // never be rendered as the result for «мигрень».
    expect(older).not.toEqual(newer);
    expect(newer[3]).toBe("мигрень");
  });

  it("scopes suggestions to profile and section", () => {
    expect(clinicalSuggestionsQueryKey("p1", "conditions", "а")).not.toEqual(
      clinicalSuggestionsQueryKey("p2", "conditions", "а"),
    );
    expect(clinicalSuggestionsQueryKey("p1", "conditions", "а")).not.toEqual(
      clinicalSuggestionsQueryKey("p1", "allergies", "а"),
    );
  });

  it("uses a debounce interval that limits request volume", () => {
    expect(TYPEAHEAD_DEBOUNCE_MS).toBeGreaterThanOrEqual(150);
    expect(TYPEAHEAD_DEBOUNCE_MS).toBeLessThanOrEqual(500);
  });
});
