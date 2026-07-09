import { describe, expect, it } from "vitest";

import { resolveProfileDisplayName } from "./AppLayout";

const profile = {
  id: "11111111-1111-1111-1111-111111111111",
  workspace_id: "22222222-2222-2222-2222-222222222222",
  owner_user_id: "33333333-3333-3333-3333-333333333333",
  display_name: "Михаил",
  date_of_birth: null,
  sex: null,
  height_cm: null,
  timezone: null,
};

describe("resolveProfileDisplayName", () => {
  it("uses the health profile name instead of the technical account name", () => {
    expect(resolveProfileDisplayName([profile], "michailr", "michailr@gmail.com")).toBe("Михаил");
  });

  it("falls back to the account display name when no profile is available", () => {
    expect(resolveProfileDisplayName([], "Михаил Радин", "michailr@gmail.com")).toBe("Михаил Радин");
  });

  it("falls back to email only when neither profile nor account name exists", () => {
    expect(resolveProfileDisplayName(undefined, null, "michailr@gmail.com")).toBe("michailr@gmail.com");
  });
});
