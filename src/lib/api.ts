export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/health/api${path}`, { credentials: "include" });
  if (response.status === 401) {
    window.location.assign("/health/login");
    throw new Error("Authentication required");
  }
  if (response.status === 403) throw new Error("Нет доступа к данным");
  if (!response.ok) throw new Error(`API error ${response.status}`);
  return response.json();
}

export interface HealthProfile {
  id: string;
  workspace_id: string;
  owner_user_id: string;
  display_name: string;
  date_of_birth: string | null;
  sex: string | null;
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
