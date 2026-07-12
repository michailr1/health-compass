import { ApiError, apiGet, apiPatch, apiPost, parseApiError } from "./api";

export type OCRCandidateStatus =
  | "needs_review"
  | "accepted"
  | "edited"
  | "rejected"
  | "deferred";

export type OCRReviewStatus = "not_started" | "in_progress" | "finalized";
export type OCRReviewAction = "accept" | "edit" | "reject" | "defer";
export type OCRPatientDecision = "unknown" | "match" | "mismatch" | "not_present";

export interface OCRCandidate {
  id: string;
  run_id: string;
  document_id: string;
  profile_id: string;
  page_artifact_id: string;
  page_number: number;
  candidate_index: number;
  status: OCRCandidateStatus;
  original_text: string;
  reviewed_text: string | null;
  confidence_min: number;
  confidence_mean: number;
  left_px: number;
  top_px: number;
  width_px: number;
  height_px: number;
  source_word_count: number;
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OCRPatientDecisionRecord {
  id: string;
  run_id: string;
  document_id: string;
  profile_id: string;
  decision: OCRPatientDecision;
  note: string | null;
  decided_at: string;
  created_at: string;
  updated_at: string;
}

export interface OCRCandidateVersion {
  id: string;
  updated_at: string;
}

export interface OCRReviewState {
  document_id: string;
  profile_id: string;
  run_id: string;
  document_updated_at: string;
  ocr_status: "review_required" | "reviewed";
  review_status: OCRReviewStatus;
  candidates: OCRCandidate[];
  candidate_versions: OCRCandidateVersion[];
  patient_decision: OCRPatientDecisionRecord | null;
  unresolved_count: number;
  deferred_count: number;
  can_finalize: boolean;
  finalized_at: string | null;
}

export interface ReviewCandidatePayload {
  action: OCRReviewAction;
  reviewed_text?: string | null;
  review_note?: string | null;
  expected_updated_at: string;
}

export interface PatientDecisionPayload {
  decision: OCRPatientDecision;
  note?: string | null;
  expected_document_updated_at: string;
  expected_decision_updated_at?: string | null;
}

async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: "PUT",
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
      // Keep status-based fallback without exposing raw response text.
    }
    throw parseApiError(response.status, payload, response.headers.get("X-Request-ID"));
  }
  return response.json();
}

export function getOCRReview(
  profileId: string,
  documentId: string,
): Promise<OCRReviewState> {
  return apiGet<OCRReviewState>(
    `/profiles/${profileId}/documents/${documentId}/ocr/review`,
  );
}

export function reviewOCRCandidate(
  profileId: string,
  documentId: string,
  candidateId: string,
  payload: ReviewCandidatePayload,
): Promise<OCRReviewState> {
  return apiPatch<OCRReviewState>(
    `/profiles/${profileId}/documents/${documentId}/ocr/candidates/${candidateId}`,
    payload,
  );
}

export function setOCRPatientDecision(
  profileId: string,
  documentId: string,
  payload: PatientDecisionPayload,
): Promise<OCRReviewState> {
  return apiPut<OCRReviewState>(
    `/profiles/${profileId}/documents/${documentId}/ocr/patient-match`,
    payload,
  );
}

export function finalizeOCRReview(
  profileId: string,
  documentId: string,
  state: OCRReviewState,
): Promise<OCRReviewState> {
  return apiPost<OCRReviewState>(
    `/profiles/${profileId}/documents/${documentId}/ocr/finalize`,
    {
      expected_document_updated_at: state.document_updated_at,
      candidate_versions: state.candidate_versions,
      expected_patient_decision_updated_at: state.patient_decision?.updated_at,
    },
  );
}

export function candidateStatusLabel(status: OCRCandidateStatus): string {
  const labels: Record<OCRCandidateStatus, string> = {
    needs_review: "Нужно проверить",
    accepted: "Принято без изменений",
    edited: "Исправлено",
    rejected: "Исключено",
    deferred: "Отложено",
  };
  return labels[status];
}

export function patientDecisionLabel(decision: OCRPatientDecision): string {
  const labels: Record<OCRPatientDecision, string> = {
    unknown: "Не указано",
    match: "Документ относится к этому профилю",
    mismatch: "Документ относится к другому человеку",
    not_present: "Имя пациента в документе не указано",
  };
  return labels[decision];
}
