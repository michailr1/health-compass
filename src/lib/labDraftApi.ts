import { ApiError, apiGet, apiPatch, apiPost, parseApiError } from "./api";
import type { OCRCandidate } from "./documentOcrReviewApi";

export type LabValueKind = "numeric" | "text" | "qualitative";
export type LabDraftStatus = "draft" | "ready" | "rejected" | "confirmed";
export type LabSourceRole =
  | "analyte"
  | "value"
  | "unit"
  | "reference_range"
  | "observed_at"
  | "specimen"
  | "flag"
  | "comment";

export interface LabDraftFields {
  source_analyte_text: string;
  source_value_text: string;
  value_kind: LabValueKind;
  comparator?: "<" | "<=" | "=" | ">=" | ">" | null;
  numeric_value?: string | null;
  text_value?: string | null;
  qualitative_value_text?: string | null;
  source_unit_text?: string | null;
  unit_not_present: boolean;
  source_reference_range_text?: string | null;
  reference_range_not_present: boolean;
  source_observed_at_text?: string | null;
  observed_time_unknown: boolean;
  observed_date?: string | null;
  observed_at?: string | null;
  observed_precision: "unknown" | "date" | "datetime";
  source_specimen_text?: string | null;
  source_flag_text?: string | null;
  source_comment?: string | null;
}

export interface LabDraftSource {
  candidate_id: string;
  source_role: LabSourceRole;
  candidate_updated_at: string;
  page_artifact_id: string;
  page_number: number;
}

export interface LabDraft extends LabDraftFields {
  id: string;
  profile_id: string;
  document_id: string;
  ocr_run_id: string;
  patient_decision_id: string;
  status: LabDraftStatus;
  sources: LabDraftSource[];
  confirmed_at?: string | null;
  confirmed_observation_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LabDraftContext {
  document_id: string;
  profile_id: string;
  document_updated_at: string;
  ocr_run_id: string;
  review_finalized_at: string;
  patient_decision_id: string;
  patient_decision: "match" | "not_present";
  patient_decision_updated_at: string;
  candidates: OCRCandidate[];
}

export interface LabObservationSource {
  candidate_id: string;
  source_role: LabSourceRole;
  candidate_updated_at: string;
  page_artifact_id: string;
  page_number: number;
  reviewed_text_snapshot: string;
}

export interface LabObservation extends LabDraftFields {
  id: string;
  profile_id: string;
  document_id: string;
  ocr_run_id: string;
  patient_decision_id: string;
  source_draft_id: string;
  status: "active";
  patient_decision: "match" | "not_present";
  sources: LabObservationSource[];
  source_draft_updated_at: string;
  source_document_updated_at: string;
  source_review_finalized_at: string;
  source_patient_decision_updated_at: string;
  confirmed_by_user_id: string;
  confirmed_at: string;
  created_at: string;
}

export interface LabConfirmationPreview {
  draft: LabDraft;
  patient_decision: "match" | "not_present";
  requires_not_present_assignment_ack: boolean;
  expected_document_updated_at: string;
  expected_review_finalized_at: string;
  expected_patient_decision_updated_at: string;
}

export interface LabConfirmationAcknowledgements {
  acknowledge_source_matches: boolean;
  acknowledge_unit_and_range: boolean;
  acknowledge_observed_at: boolean;
  acknowledge_profile: boolean;
  acknowledge_structured_record: boolean;
  acknowledge_not_present_assignment: boolean;
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
      // Keep the structured status fallback.
    }
    throw parseApiError(response.status, payload, response.headers.get("X-Request-ID"));
  }
  return response.json();
}

function basePath(profileId: string, documentId: string): string {
  return `/profiles/${profileId}/documents/${documentId}/lab-drafts`;
}

function contextVersions(context: LabDraftContext) {
  return {
    expected_document_updated_at: context.document_updated_at,
    expected_review_finalized_at: context.review_finalized_at,
    expected_patient_decision_updated_at: context.patient_decision_updated_at,
  };
}

export function getLabDraftContext(
  profileId: string,
  documentId: string,
): Promise<LabDraftContext> {
  return apiGet<LabDraftContext>(`${basePath(profileId, documentId)}/context`);
}

export function listLabDrafts(
  profileId: string,
  documentId: string,
): Promise<LabDraft[]> {
  return apiGet<LabDraft[]>(basePath(profileId, documentId));
}

export function createLabDraft(
  profileId: string,
  documentId: string,
  context: LabDraftContext,
  fields: LabDraftFields,
): Promise<LabDraft> {
  return apiPost<LabDraft>(basePath(profileId, documentId), {
    ...contextVersions(context),
    fields,
  });
}

export function updateLabDraft(
  profileId: string,
  documentId: string,
  context: LabDraftContext,
  draft: LabDraft,
  fields: LabDraftFields,
): Promise<LabDraft> {
  return apiPatch<LabDraft>(`${basePath(profileId, documentId)}/${draft.id}`, {
    expected_updated_at: draft.updated_at,
    ...contextVersions(context),
    fields,
  });
}

export function setLabDraftSources(
  profileId: string,
  documentId: string,
  context: LabDraftContext,
  draft: LabDraft,
  sources: Array<{
    candidate_id: string;
    source_role: LabSourceRole;
    expected_updated_at: string;
  }>,
): Promise<LabDraft> {
  return apiPut<LabDraft>(`${basePath(profileId, documentId)}/${draft.id}/sources`, {
    expected_updated_at: draft.updated_at,
    ...contextVersions(context),
    sources,
  });
}

export function setLabDraftStatus(
  profileId: string,
  documentId: string,
  context: LabDraftContext,
  draft: LabDraft,
  status: "ready" | "rejected",
): Promise<LabDraft> {
  return apiPost<LabDraft>(`${basePath(profileId, documentId)}/${draft.id}/status`, {
    status,
    expected_updated_at: draft.updated_at,
    ...contextVersions(context),
  });
}

export function getLabConfirmationPreview(
  profileId: string,
  documentId: string,
  draftId: string,
): Promise<LabConfirmationPreview> {
  return apiGet<LabConfirmationPreview>(
    `${basePath(profileId, documentId)}/${draftId}/confirmation`,
  );
}

export function confirmLabObservation(
  profileId: string,
  documentId: string,
  preview: LabConfirmationPreview,
  acknowledgements: LabConfirmationAcknowledgements,
  idempotencyKey: string,
): Promise<LabObservation> {
  return apiPost<LabObservation>(
    `${basePath(profileId, documentId)}/${preview.draft.id}/confirm`,
    {
      idempotency_key: idempotencyKey,
      expected_draft_updated_at: preview.draft.updated_at,
      expected_document_updated_at: preview.expected_document_updated_at,
      expected_review_finalized_at: preview.expected_review_finalized_at,
      expected_patient_decision_updated_at:
        preview.expected_patient_decision_updated_at,
      ...acknowledgements,
    },
  );
}

export function listLabObservations(profileId: string): Promise<LabObservation[]> {
  return apiGet<LabObservation[]>(`/profiles/${profileId}/lab-observations`);
}

export function getLabObservation(
  profileId: string,
  observationId: string,
): Promise<LabObservation> {
  return apiGet<LabObservation>(
    `/profiles/${profileId}/lab-observations/${observationId}`,
  );
}

export function labDraftStatusLabel(status: LabDraftStatus): string {
  const labels: Record<LabDraftStatus, string> = {
    draft: "Черновик",
    ready: "Готово к отдельному подтверждению",
    rejected: "Исключено",
    confirmed: "Подтверждено",
  };
  return labels[status];
}
