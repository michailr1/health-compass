import { ApiError, apiGet, parseApiError } from "./api";

export type DocumentStatus =
  | "uploading"
  | "quarantined"
  | "scanning"
  | "accepted"
  | "ocr_queued"
  | "processing"
  | "review_required"
  | "confirmed"
  | "rejected"
  | "failed"
  | "voided"
  | "deletion_pending"
  | "erased";

export type ScannerStatus =
  | "not_scanned"
  | "scanning"
  | "clean"
  | "infected"
  | "error"
  | "stale";

export type RenderStatus =
  | "not_started"
  | "queued"
  | "rendering"
  | "ready"
  | "error";

export type OCRStatus =
  | "not_started"
  | "queued"
  | "processing"
  | "review_required"
  | "reviewed"
  | "error";

export interface ProfileDocument {
  id: string;
  profile_id: string;
  status: DocumentStatus;
  scanner_status: ScannerStatus;
  render_status: RenderStatus;
  ocr_status: OCRStatus;
  original_filename: string;
  declared_media_type: string;
  detected_media_type: string;
  byte_size: number;
  page_count: number | null;
  failure_code: string | null;
  created_at: string;
  updated_at: string;
  voided_at: string | null;
}

export interface DocumentIntakeCapabilities {
  upload_enabled: boolean;
  accepted_media_types: string[];
  max_bytes: number;
  max_image_pixels: number;
  quarantine_only: true;
  preview_available: false;
  ocr_available: boolean;
}

export interface DocumentOCRStatus {
  document_id: string;
  profile_id: string;
  status: OCRStatus;
  run_id: string | null;
  run_status: "queued" | "leased" | "succeeded" | "failed" | "cancelled" | null;
  review_status: "not_started" | "in_progress" | "finalized" | null;
  attempt: number | null;
  language_spec: string | null;
  psm: number | null;
  engine_name: string | null;
  engine_version: string | null;
  candidate_count: number;
  needs_review_count: number;
  completed_at: string | null;
  review_finalized_at: string | null;
  safe_error_code: string | null;
}

export const DOCUMENT_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

export function listDocuments(profileId: string): Promise<ProfileDocument[]> {
  return apiGet<ProfileDocument[]>(`/profiles/${profileId}/documents`);
}

export function getDocumentIntakeCapabilities(
  profileId: string,
): Promise<DocumentIntakeCapabilities> {
  return apiGet<DocumentIntakeCapabilities>(
    `/profiles/${profileId}/document-intake/capabilities`,
  );
}

export function getDocumentOCRStatus(
  profileId: string,
  documentId: string,
): Promise<DocumentOCRStatus> {
  return apiGet<DocumentOCRStatus>(
    `/profiles/${profileId}/documents/${documentId}/ocr/status`,
  );
}

export async function uploadProfileDocument(
  profileId: string,
  file: File,
): Promise<ProfileDocument> {
  const form = new FormData();
  form.append("file", file, file.name);

  const response = await fetch(`/api/profiles/${profileId}/documents`, {
    method: "POST",
    credentials: "include",
    body: form,
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
      // Keep the status-based fallback without exposing raw response text.
    }
    throw parseApiError(response.status, payload, response.headers.get("X-Request-ID"));
  }
  return response.json();
}

export function formatDocumentSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

export function documentStatusLabel(status: DocumentStatus): string {
  const labels: Record<DocumentStatus, string> = {
    uploading: "Загружается",
    quarantined: "Идёт проверка файла",
    scanning: "Идёт проверка файла",
    accepted: "Проверка завершена",
    ocr_queued: "В очереди на распознавание",
    processing: "Обрабатывается",
    review_required: "Нужно проверить",
    confirmed: "Подтверждён",
    rejected: "Отклонён",
    failed: "Ошибка обработки",
    voided: "Убран из профиля",
    deletion_pending: "Удаляется",
    erased: "Удалён",
  };
  return labels[status];
}

export function scannerStatusLabel(status: ScannerStatus): string {
  const labels: Record<ScannerStatus, string> = {
    not_scanned: "Ожидает проверки файла",
    scanning: "Идёт проверка файла",
    clean: "Проверка завершена",
    infected: "Отклонён как небезопасный",
    error: "Проверка временно не завершена",
    stale: "Ожидает повторной проверки",
  };
  return labels[status];
}

export function renderStatusLabel(status: RenderStatus): string {
  const labels: Record<RenderStatus, string> = {
    not_started: "Ожидает обработки",
    queued: "В очереди на обработку",
    rendering: "Файл обрабатывается",
    ready: "Файл подготовлен",
    error: "Не удалось обработать файл",
  };
  return labels[status];
}

export function ocrStatusLabel(status: OCRStatus): string {
  const labels: Record<OCRStatus, string> = {
    not_started: "Распознавание не начато",
    queued: "В очереди на распознавание",
    processing: "Распознаётся",
    review_required: "Текст нужно проверить",
    reviewed: "Проверка текста завершена",
    error: "Распознавание не завершено",
  };
  return labels[status];
}
