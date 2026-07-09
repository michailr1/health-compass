export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
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
  if (response.status === 403) throw new ApiError(403, "Нет доступа к данным");
  if (!response.ok) {
    let message = `API error ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") message = payload.detail;
    } catch {
      // Keep the status-based fallback.
    }
    throw new ApiError(response.status, message);
  }
  return response.json();
}

export function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path);
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
