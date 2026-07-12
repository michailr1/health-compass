import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Archive, Loader2, Trash2 } from "lucide-react";

import type { ClinicalRecord, SectionKey } from "@/components/ClinicalContextSection";
import { useAuth } from "@/context/AuthContext";
import { ApiError, apiGet, apiPost, type HealthProfile } from "@/lib/api";
import { apiDelete } from "@/lib/apiDelete";

export function isPermanentErasureOwner(
  currentUserId: string | null | undefined,
  ownerUserId: string | null | undefined,
): boolean {
  return Boolean(currentUserId && ownerUserId && currentUserId === ownerUserId);
}

export function buildPermanentErasurePayload(record: Pick<ClinicalRecord, "updated_at">) {
  return {
    expected_updated_at: record.updated_at,
    confirm_permanent_deletion: true as const,
  };
}

function actionErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return "Запись уже изменилась. Обновите страницу и повторите действие.";
    }
    return error.requestId ? `${error.message} (код запроса: ${error.requestId})` : error.message;
  }
  return error instanceof Error ? error.message : "Не удалось выполнить действие.";
}

export function ClinicalRecordActions({
  profileId,
  section,
  record,
  onSaved,
}: {
  profileId: string;
  section: SectionKey;
  record: ClinicalRecord;
  onSaved: () => void;
}) {
  const { user } = useAuth();
  const [confirmation, setConfirmation] = useState<"none" | "archive" | "erase">("none");
  const { data: profile } = useQuery({
    queryKey: ["health-profile-owner", profileId],
    queryFn: () => apiGet<HealthProfile>(`/profiles/${profileId}`),
    staleTime: 5 * 60 * 1000,
  });
  const isOwner = isPermanentErasureOwner(user?.id, profile?.owner_user_id);

  const archiveMutation = useMutation({
    mutationFn: () =>
      apiPost(`/profiles/${profileId}/${section}/${record.id}/void`, {
        reason: "Убрано пользователем из профиля",
        expected_updated_at: record.updated_at,
      }),
    onSuccess: () => {
      setConfirmation("none");
      onSaved();
    },
  });

  const eraseMutation = useMutation({
    mutationFn: () =>
      apiDelete(
        `/profiles/${profileId}/${section}/${record.id}`,
        buildPermanentErasurePayload(record),
      ),
    onSuccess: () => {
      setConfirmation("none");
      onSaved();
    },
  });

  const pending = archiveMutation.isPending || eraseMutation.isPending;
  const error = archiveMutation.error ?? eraseMutation.error;

  if (confirmation === "archive") {
    return (
      <div className="mt-3 rounded-xl border border-border bg-background p-3">
        <p className="text-xs leading-5 text-muted-foreground">
          Запись исчезнет из профиля, но останется в защищённой истории изменений.
        </p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button
            type="button"
            disabled={pending}
            onClick={() => archiveMutation.mutate()}
            className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium disabled:opacity-50"
          >
            {archiveMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Убрать
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => setConfirmation("none")}
            className="min-h-10 rounded-lg px-3 py-2 text-xs text-muted-foreground disabled:opacity-50"
          >
            Отмена
          </button>
        </div>
        {error && <p className="mt-2 text-xs text-destructive" role="alert">{actionErrorMessage(error)}</p>}
      </div>
    );
  }

  if (confirmation === "erase") {
    return (
      <div className="mt-3 rounded-xl border border-destructive/40 bg-destructive/5 p-3">
        <p className="text-sm font-medium text-destructive">Удалить запись навсегда?</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          Запись и содержащие её медицинские значения в журнале изменений будут удалены. Отменить это действие нельзя.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            disabled={pending}
            onClick={() => eraseMutation.mutate()}
            className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg bg-destructive px-3 py-2 text-xs font-medium text-destructive-foreground disabled:opacity-50"
          >
            {eraseMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Удалить навсегда
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => setConfirmation("none")}
            className="min-h-10 rounded-lg border border-border px-3 py-2 text-xs disabled:opacity-50"
          >
            Отмена
          </button>
        </div>
        {error && <p className="mt-2 text-xs text-destructive" role="alert">{actionErrorMessage(error)}</p>}
      </div>
    );
  }

  return (
    <div className="mt-2 flex flex-wrap gap-3 border-t border-border/50 pt-2">
      <button
        type="button"
        disabled={pending}
        onClick={() => setConfirmation("archive")}
        className="inline-flex min-h-9 items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
      >
        <Archive className="h-3.5 w-3.5" aria-hidden="true" />
        Убрать из профиля
      </button>
      {isOwner && (
        <button
          type="button"
          disabled={pending}
          onClick={() => setConfirmation("erase")}
          className="inline-flex min-h-9 items-center gap-1.5 text-xs text-destructive hover:underline disabled:opacity-50"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
          Удалить навсегда
        </button>
      )}
      {error && <p className="w-full text-xs text-destructive" role="alert">{actionErrorMessage(error)}</p>}
    </div>
  );
}
