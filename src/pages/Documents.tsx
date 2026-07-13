import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ClipboardCheck,
  FileText,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { ApiError, apiGet, type HealthProfile } from "@/lib/api";
import {
  DOCUMENT_ACCEPT,
  documentStatusLabel,
  formatDocumentSize,
  getDocumentIntakeCapabilities,
  listDocuments,
  ocrStatusLabel,
  renderStatusLabel,
  scannerStatusLabel,
  type DocumentStatus,
  type OCRStatus,
  type RenderStatus,
  type ScannerStatus,
  uploadProfileDocument,
} from "@/lib/documentApi";
import { ANALYSES_EMPTY_STATE_COPY, SECURE_ANALYSES_COPY } from "@/lib/productUx";

const statusTone: Record<DocumentStatus, string> = {
  uploading: "border-border bg-muted/40 text-muted-foreground",
  quarantined: "border-warning/30 bg-warning/10 text-warning",
  scanning: "border-warning/30 bg-warning/10 text-warning",
  accepted: "border-success/30 bg-success/10 text-success",
  ocr_queued: "border-border bg-muted/40 text-muted-foreground",
  processing: "border-primary/30 bg-primary/10 text-primary",
  review_required: "border-warning/30 bg-warning/10 text-warning",
  confirmed: "border-success/30 bg-success/10 text-success",
  rejected: "border-destructive/30 bg-destructive/10 text-destructive",
  failed: "border-destructive/30 bg-destructive/10 text-destructive",
  voided: "border-border bg-muted/40 text-muted-foreground",
  deletion_pending: "border-destructive/30 bg-destructive/10 text-destructive",
  erased: "border-border bg-muted/40 text-muted-foreground",
};

const scannerTone: Record<ScannerStatus, string> = {
  not_scanned: "border-warning/30 bg-warning/10 text-warning",
  scanning: "border-primary/30 bg-primary/10 text-primary",
  clean: "border-success/30 bg-success/10 text-success",
  infected: "border-destructive/30 bg-destructive/10 text-destructive",
  error: "border-warning/30 bg-warning/10 text-warning",
  stale: "border-warning/30 bg-warning/10 text-warning",
};

const renderTone: Record<RenderStatus, string> = {
  not_started: "border-border bg-muted/40 text-muted-foreground",
  queued: "border-warning/30 bg-warning/10 text-warning",
  rendering: "border-primary/30 bg-primary/10 text-primary",
  ready: "border-success/30 bg-success/10 text-success",
  error: "border-destructive/30 bg-destructive/10 text-destructive",
};

const ocrTone: Record<OCRStatus, string> = {
  not_started: "border-border bg-muted/40 text-muted-foreground",
  queued: "border-warning/30 bg-warning/10 text-warning",
  processing: "border-primary/30 bg-primary/10 text-primary",
  review_required: "border-warning/30 bg-warning/10 text-warning",
  reviewed: "border-success/30 bg-success/10 text-success",
  error: "border-destructive/30 bg-destructive/10 text-destructive",
};

function uploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return "Для загрузки результатов анализов нужно согласие на обработку данных.";
    }
    if (error.status === 413) {
      return "Файл превышает безопасный лимит размера или разрешения.";
    }
    if (error.status === 507) {
      return "Для загрузки файла временно недостаточно места.";
    }
    if (error.status === 503) {
      return "Загрузка анализов пока отключена.";
    }
    return error.message;
  }
  return "Не удалось загрузить файл.";
}

function mediaTypeLabel(mediaType: string): string {
  const labels: Record<string, string> = {
    "application/pdf": "PDF",
    "image/jpeg": "JPEG",
    "image/png": "PNG",
  };
  return labels[mediaType] ?? "Файл";
}

function displayStatus(document: {
  status: DocumentStatus;
  scanner_status: ScannerStatus;
  render_status: RenderStatus;
  ocr_status: OCRStatus;
}): { label: string; tone: string } {
  if (
    document.status === "rejected" ||
    document.status === "failed" ||
    document.status === "voided" ||
    document.status === "deletion_pending" ||
    document.status === "erased"
  ) {
    return {
      label: documentStatusLabel(document.status),
      tone: statusTone[document.status],
    };
  }
  if (document.scanner_status !== "clean") {
    return {
      label: scannerStatusLabel(document.scanner_status),
      tone: scannerTone[document.scanner_status],
    };
  }
  if (document.render_status !== "ready") {
    return {
      label: renderStatusLabel(document.render_status),
      tone: renderTone[document.render_status],
    };
  }
  if (document.ocr_status !== "not_started") {
    return {
      label: ocrStatusLabel(document.ocr_status),
      tone: ocrTone[document.ocr_status],
    };
  }
  return {
    label: renderStatusLabel(document.render_status),
    tone: renderTone[document.render_status],
  };
}

export default function Documents() {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const { data: profiles, isLoading: profilesLoading } = useQuery({
    queryKey: ["health-profiles", "documents"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
  });
  const profile = profiles?.[0] ?? null;

  const { data: capabilities, isLoading: capabilitiesLoading } = useQuery({
    queryKey: ["document-intake-capabilities", profile?.id],
    queryFn: () => getDocumentIntakeCapabilities(profile!.id),
    enabled: Boolean(profile),
  });

  const { data: documents, isLoading: documentsLoading } = useQuery({
    queryKey: ["profile-documents", profile?.id],
    queryFn: () => listDocuments(profile!.id),
    enabled: Boolean(profile),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadProfileDocument(profile!.id, file),
    onSuccess: async () => {
      setSelectedFile(null);
      if (inputRef.current) inputRef.current.value = "";
      await queryClient.invalidateQueries({
        queryKey: ["profile-documents", profile?.id],
      });
      toast.success("Файл загружен и передан на проверку");
    },
    onError: (error) => toast.error(uploadErrorMessage(error)),
  });

  function submitUpload() {
    if (!profile || !selectedFile || !capabilities?.upload_enabled) return;
    if (selectedFile.size > capabilities.max_bytes) {
      toast.error(`Максимальный размер — ${formatDocumentSize(capabilities.max_bytes)}.`);
      return;
    }
    if (
      selectedFile.type &&
      !capabilities.accepted_media_types.includes(selectedFile.type)
    ) {
      toast.error("Поддерживаются только PDF, JPEG и PNG.");
      return;
    }
    uploadMutation.mutate(selectedFile);
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">
          Анализы
        </h1>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
          {ANALYSES_EMPTY_STATE_COPY}
        </p>
      </header>

      <section className="hm-card p-5 md:p-6">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-primary/20 bg-primary/10">
            <ShieldCheck className="h-5 w-5 text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-lg font-semibold">Загрузка результатов</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
              {SECURE_ANALYSES_COPY}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              Поддерживаются PDF, JPEG и PNG до {formatDocumentSize(capabilities?.max_bytes ?? 20 * 1024 * 1024)}.
            </p>

            {capabilitiesLoading && profile && (
              <p className="mt-4 text-sm text-muted-foreground">Проверяю доступность загрузки…</p>
            )}

            {!capabilitiesLoading && capabilities && !capabilities.upload_enabled && (
              <div className="mt-4 flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Загрузка анализов временно недоступна.</span>
              </div>
            )}

            {capabilities?.upload_enabled && (
              <div className="mt-5 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium">Выберите файл</span>
                  <input
                    ref={inputRef}
                    type="file"
                    accept={DOCUMENT_ACCEPT}
                    disabled={uploadMutation.isPending}
                    onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                    className="block w-full rounded-xl border border-border bg-background px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-primary disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <button
                  type="button"
                  onClick={submitUpload}
                  disabled={!profile || !selectedFile || uploadMutation.isPending}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Upload className="h-4 w-4" />
                  {uploadMutation.isPending ? "Загрузка…" : "Загрузить"}
                </button>
              </div>
            )}

            {selectedFile && capabilities?.upload_enabled && (
              <p className="mt-2 text-xs text-muted-foreground">
                Выбран: {selectedFile.name} · {formatDocumentSize(selectedFile.size)}
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="font-display text-lg font-semibold">Добавленные анализы</h2>
          <p className="text-sm text-muted-foreground">
            Здесь видны файлы и понятные этапы их проверки и подтверждения.
          </p>
        </div>

        {(profilesLoading || documentsLoading) && (
          <div className="hm-card p-5 text-sm text-muted-foreground">Загрузка списка…</div>
        )}

        {!profilesLoading && !profile && (
          <div className="hm-card p-5 text-sm text-muted-foreground">
            Профиль здоровья не найден.
          </div>
        )}

        {!documentsLoading && profile && documents?.length === 0 && (
          <div className="hm-card p-6 text-center">
            <FileText className="mx-auto h-8 w-8 text-muted-foreground" />
            <p className="mt-3 font-medium">Анализов пока нет</p>
            <p className="mx-auto mt-1 max-w-xl text-sm leading-6 text-muted-foreground">
              {capabilities?.upload_enabled
                ? "Загрузите PDF или фото результатов анализов, затем проверьте и подтвердите распознанные значения."
                : "Когда загрузка станет доступна, здесь появятся файлы, этапы проверки и подтверждённые результаты."}
            </p>
          </div>
        )}

        <div className="grid gap-3">
          {documents?.map((document) => {
            const currentStatus = displayStatus(document);
            const reviewAvailable = ["review_required", "reviewed"].includes(
              document.ocr_status,
            );
            return (
              <article key={document.id} className="hm-card p-4 md:p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-border bg-surface-2">
                      <FileText className="h-5 w-5 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="truncate font-medium">{document.original_filename}</h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatDocumentSize(document.byte_size)} · {mediaTypeLabel(document.detected_media_type)}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Загружен {new Date(document.created_at).toLocaleString("ru-RU")}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium ${currentStatus.tone}`}
                  >
                    {currentStatus.label}
                  </span>
                </div>
                {reviewAvailable && (
                  <Link
                    to={`/app/documents/${document.id}/review`}
                    className="mt-4 inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/15"
                  >
                    <ClipboardCheck className="h-4 w-4" />
                    {document.ocr_status === "reviewed"
                      ? "Открыть результат проверки"
                      : "Проверить распознанный текст"}
                  </Link>
                )}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
