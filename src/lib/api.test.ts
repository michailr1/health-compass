import { describe, expect, it } from "vitest";

import { ApiError, parseApiError } from "./api";

describe("parseApiError (HC-015 Slice F / CR-11)", () => {
  it("reads the structured backend envelope and keeps request_id", () => {
    const error = parseApiError(500, {
      error: {
        code: "internal_error",
        message: "An internal error occurred",
        request_id: "550e8400-e29b-41d4-a716-446655440000",
      },
    });
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(500);
    expect(error.code).toBe("internal_error");
    expect(error.message).toBe("An internal error occurred");
    expect(error.requestId).toBe("550e8400-e29b-41d4-a716-446655440000");
  });

  it("reads plain HTTPException string detail", () => {
    const error = parseApiError(409, { detail: "section_has_entries" });
    expect(error.message).toBe("section_has_entries");
    expect(error.code).toBeNull();
  });

  it("reads a nested detail.error envelope", () => {
    const error = parseApiError(401, {
      detail: { error: { code: "unauthorized", message: "Authentication required", request_id: "rid-1" } },
    });
    expect(error.code).toBe("unauthorized");
    expect(error.message).toBe("Authentication required");
    expect(error.requestId).toBe("rid-1");
  });

  it("falls back to the X-Request-ID header when the body has none", () => {
    const error = parseApiError(409, { detail: "conflict" }, "header-request-id");
    expect(error.requestId).toBe("header-request-id");
  });

  it("never exposes raw payloads for unknown shapes", () => {
    const error = parseApiError(500, { traceback: 'File "app.py", line 1' });
    expect(error.message).toBe("API error 500");
    expect(error.message).not.toContain("File");
  });

  it("survives non-JSON payloads", () => {
    const error = parseApiError(502, null);
    expect(error.message).toBe("API error 502");
    expect(error.requestId).toBeNull();
  });
});
