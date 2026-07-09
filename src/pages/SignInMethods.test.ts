import { describe, expect, it } from "vitest";

import { getMissingProvider, type SignInMethod } from "./SignInMethods";

function method(provider: string): SignInMethod {
  return {
    id: `${provider}-id`,
    provider,
    label: `${provider}@example.com`,
    verified: true,
    connected_at: "2026-07-09T00:00:00Z",
    last_seen_at: null,
    can_remove: false,
  };
}

describe("getMissingProvider", () => {
  it("offers Email Magic Link when only Google is connected", () => {
    expect(getMissingProvider([method("google")])).toBe("email");
  });

  it("offers Google when only Email Magic Link is connected", () => {
    expect(getMissingProvider([method("email")])).toBe("google");
  });

  it("offers nothing when both supported methods are connected", () => {
    expect(getMissingProvider([method("google"), method("email")])).toBeNull();
  });

  it("offers nothing for an empty or unsupported-only method list", () => {
    expect(getMissingProvider([])).toBeNull();
    expect(getMissingProvider([method("future-provider")])).toBeNull();
  });
});
