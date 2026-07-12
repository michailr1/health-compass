import { useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ApiError, apiGet, type HealthProfile } from "@/lib/api";
import {
  confirmLabObservation,
  getLabConfirmationPreview,
  type LabConfirmationAcknowledgements,
  type LabObservation,
} from "@/lib/labDraftApi";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return "Черновик или исходный документ изменились. Обновите страницу и проверьте данные ещё раз.";
    }
    if (error.status === 422) {
      return "Нужно подтвердить все обязательные пункты.";
    }
    if (error.status === 428) {
      return "Не хватает версии исходных данных для безопасного подтверждения.";
    }
    return error.message;
  }
  return "Не удалось создать подтверждённую запись.";
}

function CheckRow({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border p-3 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 h-4 w-4"
      />
      <span>{children}</span>
    </label>
  );
}

export default function LabObservationConfirm() {
  const { documentId, draftId } = useParams<{
    documentId: string;
    draftId: string;
  }>();
  const [idempotencyKey] = useState(() => crypto.randomUUID());
  const [acknowledgements, setAcknowledgements] =
    useState<LabConfirmationAcknowledgements>({
      acknowledge_source_matches: false,
      acknowledge_unit_and_range: false,
      acknowledge_observed_at: false,
      acknowledge_profile: false,
      acknowledge_structured_record: false,
      acknowledge_not_present_assignment: false,
    });
  const [confirmed, setConfirmed] = useState<LabObservation | null>(null);

  const profilesQuery = useQuery({
    queryKey: ["health-profiles", "lab-confirmation"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
  });
  const profile = profilesQuery.data?.[0] ?? null;

  const previewQuery = useQuery({
    queryKey: ["lab-confirmation-preview", profile?.id, documentId, draftId],
    queryFn: () =>
      getLabConfirmationPreview(profile!.id, documentId!, draftId!),
    enabled: Boolean(profile && documentId && draftId),
  });
  const preview = previewQuery.data;

  const confirmMutation = useMutation({
    mutationFn: () =>
      confirmLabObservation(
        profile!.id,
        documentId!,
        preview!,
        acknowledgements,
        idempotencyKey,
      ),
    onSuccess: (observation) => {
      setConfirmed(observation);
      toast.success("Подтверждённая лабораторная запись создана");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  if (profilesQuery.isLoading || previewQuery.isLoading) {
    return (
      <div className="hm-card p-5 text-sm text-muted-foreground">Загрузка…</div>
    );
  }

  if (!profile || !documentId || !draftId || !preview || previewQuery.isError) {
    return (
      <div className="space-y-4">
        <Link
          to={documentId ? `/app/documents/${documentId}/labs` : "/app/documents"}
          className="inline-flex items-center gap-2 text-sm text-primary"
        >
          <ArrowLeft className="h-4 w-4" /> Назад
        </Link>
        <div className="hm-card p-5 text-sm text-destructive">
          Подтверждение недоступно. Черновик мог измениться или уже быть
          подтверждён.
        </div>
      </div>
    );
  }

  if (confirmed) {
    return (
      <div className="space-y-5">
        <Link
          to={`/app/documents/${documentId}/labs`}
          className="inline-flex items-center gap-2 text-sm text-primary"
        >
          <ArrowLeft className="h-4 w-4" /> К лабораторным записям
        </Link>
        <section className="hm-card p-6">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-6 w-6 text-primary" />
            <div>
              <h1 className="font-display text-2xl font-semibold">
                Лабораторная запись подтверждена
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Сохранён неизменяемый снимок значения и его источников.
                Медицинская интерпретация не выполнялась.
              </p>
              <dl className="mt-5 grid gap-3 text-sm md:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Показатель</dt>
                  <dd className="font-medium">
                    {confirmed.source_analyte_text}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">
                    Значение из источника
                  </dt>
                  <dd className="font-medium">{confirmed.source_value_text}</dd>
                </div>
              </dl>
            </div>
          </div>
        </section>
      </div>
    );
  }

  const draft = preview.draft;
  const requiredAcknowledged =
    acknowledgements.acknowledge_source_matches &&
    acknowledgements.acknowledge_unit_and_range &&
    acknowledgements.acknowledge_observed_at &&
    acknowledgements.acknowledge_profile &&
    acknowledgements.acknowledge_structured_record &&
    (!preview.requires_not_present_assignment_ack ||
      acknowledgements.acknowledge_not_present_assignment);

  const setAck = (
    key: keyof LabConfirmationAcknowledgements,
    value: boolean,
  ) => {
    setAcknowledgements((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="space-y-6">
      <Link
        to={`/app/documents/${documentId}/labs`}
        className="inline-flex items-center gap-2 text-sm text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> Назад к черновикам
      </Link>

      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">
          Подтверждение лабораторной записи
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Проверьте источник и подтвердите создание структурированной записи.
          Это действие не определяет норму, диагноз или лечение.
        </p>
      </header>

      <section className="hm-card p-5 md:p-6">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div className="w-full">
            <h2 className="font-display text-lg font-semibold">
              Неизменяемый снимок источника
            </h2>
            <dl className="mt-4 grid gap-4 text-sm md:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">Профиль</dt>
                <dd className="font-medium">{profile.display_name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Решение о пациенте</dt>
                <dd className="font-medium">
                  {preview.patient_decision === "match"
                    ? "Пациент совпадает с профилем"
                    : "Пациент в источнике не указан"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">
                  Показатель как в документе
                </dt>
                <dd className="font-medium">{draft.source_analyte_text}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">
                  Значение как в документе
                </dt>
                <dd className="font-medium">{draft.source_value_text}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Единица</dt>
                <dd className="font-medium">
                  {draft.unit_not_present ? "Не указана" : draft.source_unit_text}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Референсный диапазон</dt>
                <dd className="font-medium">
                  {draft.reference_range_not_present
                    ? "Не указан"
                    : draft.source_reference_range_text}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Дата/время</dt>
                <dd className="font-medium">
                  {draft.observed_time_unknown
                    ? "Не указаны"
                    : draft.source_observed_at_text}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Фрагменты источника</dt>
                <dd className="font-medium">
                  {draft.sources.length} на странице(ах){" "}
                  {[
                    ...new Set(
                      draft.sources.map((source) => source.page_number),
                    ),
                  ].join(", ")}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      <section className="hm-card space-y-3 p-5 md:p-6">
        <h2 className="font-display text-lg font-semibold">
          Обязательные подтверждения
        </h2>
        <CheckRow
          checked={acknowledgements.acknowledge_source_matches}
          onChange={(value) => setAck("acknowledge_source_matches", value)}
        >
          Название показателя и значение соответствуют проверенному тексту
          документа.
        </CheckRow>
        <CheckRow
          checked={acknowledgements.acknowledge_unit_and_range}
          onChange={(value) => setAck("acknowledge_unit_and_range", value)}
        >
          Единица и референсный диапазон указаны верно либо их отсутствие
          отмечено явно.
        </CheckRow>
        <CheckRow
          checked={acknowledgements.acknowledge_observed_at}
          onChange={(value) => setAck("acknowledge_observed_at", value)}
        >
          Дата и время указаны верно либо их отсутствие отмечено явно.
        </CheckRow>
        <CheckRow
          checked={acknowledgements.acknowledge_profile}
          onChange={(value) => setAck("acknowledge_profile", value)}
        >
          Результат относится к выбранному профилю «{profile.display_name}».
        </CheckRow>
        <CheckRow
          checked={acknowledgements.acknowledge_structured_record}
          onChange={(value) => setAck("acknowledge_structured_record", value)}
        >
          Я понимаю, что создаётся структурированная запись, а не медицинская
          интерпретация.
        </CheckRow>
        {preview.requires_not_present_assignment_ack && (
          <CheckRow
            checked={acknowledgements.acknowledge_not_present_assignment}
            onChange={(value) =>
              setAck("acknowledge_not_present_assignment", value)
            }
          >
            Я явно назначаю этот результат выбранному профилю, хотя источник не
            идентифицирует пациента.
          </CheckRow>
        )}

        <button
          type="button"
          disabled={!requiredAcknowledged || confirmMutation.isPending}
          onClick={() => confirmMutation.mutate()}
          className="mt-2 inline-flex min-h-11 items-center justify-center rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
        >
          {confirmMutation.isPending
            ? "Подтверждение…"
            : "Создать подтверждённую медицинскую запись"}
        </button>
      </section>
    </div>
  );
}
