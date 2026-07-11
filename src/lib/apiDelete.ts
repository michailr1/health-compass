import { ApiError, parseApiError } from "@/lib/api";

/** Send an authenticated JSON DELETE request and preserve the normal API error contract. */
export async function apiDelete<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: "DELETE",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (response.status === 401) {
    window.location.assign("/login");
    throw new ApiError(401, "Authentication required");
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Keep the status-based fallback.
    }
    const error = parseApiError(response.status, payload, response.headers.get("X-Request-ID"));
    if (response.status === 403) {
      throw new ApiError(403, "Удалить запись может только владелец профиля", error.code, error.requestId);
    }
    throw error;
  }

  return response.json();
}
