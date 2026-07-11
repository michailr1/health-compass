export class ApiError extends Error {
  readonly status: number;
  /** Machine-readable error code from the backend envelope, if any. */
  readonly code: string | null;
  /** Support identifier — always preserved so users can report failures. */
  readonly requestId: string | null;

  constructor(status: number, message: string, code: string | null = null, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

interface ErrorEnvelope {
  code?: unknown;
  message?: unknown;
  request_id?: unknown;
}

/**
 * The backend uses two documented error shapes:
 *  1. global handlers:      {"error": {"code", "message", "request_id"}}
 *  2. route HTTPException:  {"detail": "..."} or {"detail": {"error": {...}}}
 * Normalize both, never surfacing stack traces or raw payloads.
 */
export function parseApiError(
  status: number,
  payload: unknown,
  headerRequestId: string | null = null,
): ApiError {
  let envelope: ErrorEnvelope | null = null;
  let detailMessage: string | null = null;

  if (payload && typeof payload === "object") {
    const body = payload as { error?: unknown; detail?: unknown };
    if (body.error && typeof body.error === "object") {
      envelope = body.error as ErrorEnvelope;
    } else if (typeof body.detail === "string") {
      detailMessage = body.detail;
    } else if (body.detail && typeof body.detail === "object") {
      const nested = (body.detail as { error?: unknown }).error;
      if (nested && typeof nested === "object") envelope = nested as ErrorEnvelope;
    }
  }

  const message =
    (typeof envelope?.message === "string" && envelope.message) ||
    detailMessage ||
    `API error ${status}`;
  const code = typeof envelope?.code === "string" ? envelope.code : null;
  const requestId =
    (typeof envelope?.request_id === "string" && envelope.request_id) || headerRequestId;
  return new ApiError(status, message, code, requestId);
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
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
      throw new ApiError(403, "Нет доступа к данным", error.code, error.requestId);
    }
    throw error;
  }
  return response.json();
}

export function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, init);
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export interface ProfileReadiness {
  age_references: boolean;
  sex_specific_references: boolean;
  bmi: boolean;
  local_time_context: boolean;
  missing_fields: string[];
}

export interface HealthProfile {
  id: string;
  workspace_id: string;
  owner_user_id: string;
  display_name: string;
  date_of_birth: string | null;
  sex: "male" | "female" | "not_specified" | null;
  height_cm: string | null;
  timezone: string | null;
  readiness?: ProfileReadiness | null;
}

export interface BodyMeasurement {
  id: string;
  profile_id: string;
  measurement_type: "weight";
  value: string;
  unit: "kg";
  measured_at: string;
  source_type: "manual";
  confirmation_status: "confirmed";
  created_by_user_id: string;
  created_at: string;
  voided_at: string | null;
  voided_by_user_id: string | null;
  void_reason: string | null;
}

export interface ConsentStatus {
  id: string | null;
  consent_type: "health_data_processing";
  document_version: string | null;
  accepted_at: string | null;
  revoked_at: string | null;
  active: boolean;
}

export type ClinicalSectionKey = "conditions" | "allergies" | "medications" | "supplements";
export type ClinicalReviewState = "unknown" | "deferred" | "confirmed_none";
export type ClinicalEffectiveState = ClinicalReviewState | "has_entries";

export interface ClinicalSectionState {
  review_state: ClinicalReviewState;
  effective_state: ClinicalEffectiveState;
  reviewed_at: string | null;
  updated_at: string | null;
  active_count: number;
  history_count: number;
}

export interface ClinicalContextSummary {
  profile_id: string;
  sections: Record<ClinicalSectionKey, ClinicalSectionState>;
}

export interface ClinicalSuggestion {
  id: string | null;
  display_text: string;
  qualifier: string | null;
  source: "global" | "personal";
  canonical_concept_id: string | null;
  matched_text: string;
}

export type ProfileCompletionState = "complete" | "deferred" | "incomplete";

export interface ProfileCompletionSection {
  key: string;
  title: string;
  state: ProfileCompletionState;
  missing_fields: string[];
  next_action: string;
}

export interface ProfileCompletionSummary {
  completed_sections: number;
  total_sections: number;
  progress_percent: number;
  next_section: string | null;
  sections: ProfileCompletionSection[];
}

export interface DashboardSnapshot {
  id: string;
  profile_id: string;
  summary: {
    observationIndex: number;
    avgSleep: { hours: number; minutes: number };
    shortNightsPct: number;
    activeDays: number;
    geneticPositions: number;
  };
  priorities: Array<{
    id: string;
    title: string;
    description: string;
    priority: "high" | "medium" | "info";
  }>;
  source_label: string;
  created_at: string;
}
