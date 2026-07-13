import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Beaker,
  History,
  PencilLine,
  Trash2,
  Undo2,
} from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { useAuth } from "@/context/AuthContext";
import { ApiError, apiGet, type HealthProfile } from "@/lib/api";
import {
  correctLabObservation,
  eraseLabObservation,
  labObservationStatusLabel,
  listLabObservationHistory,
  voidLabObservation,
  type LabDraftFields,
  type LabObservation,
  type LabValueKind,
} from "@/lib/labDraftApi";

function lifecycleError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "Запись не найдена или действие недоступно для вашей роли.";
    }
    if (error.status === 409) {
      return "Запись уже изменилась. Обновите страницу и повторите проверку.";
    }
    if (error.status === 422) return "Проверьте причину и исправленные поля.";
    if (error.status === 428) {
      return "Не хватает подтверждения или версии записи для безопасного действия.";
    }
    return error.message;
  }
  return "Не удалось изменить лабораторную запись.";
}

function fieldsFromObservation(observation: LabObservation): LabDraftFields {
  return {
    source_analyte_text: observation.source_analyte_text,
    source_value_text: observation.source_value_text,
    value_kind: observation.value_kind,
    comparator: observation.comparator ?? null,
    numeric_value: observation.numeric_value ?? null,
    text_value: observation.text_value ?? null,
    qualitative_value_text: observation.qualitative_value_text ?? null,
    source_unit_text: observation.source_unit_text ?? null,
    unit_not_present: observation.unit_not_present,
    source_reference_range_text:
      observation.source_reference_range_text ?? null,
    reference_range_not_present: observation.reference_range_not_present,
    source_observed_at_text: observation.source_observed_at_text ?? null,
    observed_time_unknown: observation.observed_time_unknown,
    observed_date: observation.observed_date ?? null,
    observed_at: observation.observed_at ?? null,
    observed_precision: observation.observed_precision,
    source_specimen_text: observation.source_specimen_text ?? null,
    source_flag_text: observation.source_flag_text ?? null,
    source_comment: observation.source_comment ?? null,
  };
}

function valueDisplay(observation: LabObservation): string {
  const unit = observation.unit_not_present
    ? ""
    : ` ${observation.source_unit_text ?? ""}`;
  return `${observation.source_value_text}${unit}`.trim();
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function LabObservations() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [correcting, setCorrecting] = useState<LabObservation | null>(null);
  const [correctionFields, setCorrectionFields] =
    useState<LabDraftFields | null>(null);
  const [correctionReason, setCorrectionReason] = useState("");
  const [voiding, setVoiding] = useState<LabObservation | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [erasing, setErasing] = useState<LabObservation | null>(null);
  const [eraseText, setEraseText] = useState("");

  const profilesQuery = useQuery({
    queryKey: ["health-profiles", "lab-observations"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
  });
  const profile = profilesQuery.data?.[0] ?? null;
  const historyKey = ["lab-observation-history", profile?.id] as const;
  const historyQuery = useQuery({
    queryKey: historyKey,
    queryFn: () => listLabObservationHistory(profile!.id),
    enabled: Boolean(profile),
  });
  const observations = historyQuery.data ?? [];
  const activeCount = useMemo(
    () => observations.filter((item) => item.status === "active").length,
    [observations],
  );
  const isOwner = Boolean(profile && user && profile.owner_user_id === user.id);

  const correctionMutation = useMutation({
    mutationFn: () => {
      if (!profile || !correcting || !correctionFields) {
        throw new Error("Correction context unavailable");
      }
      return correctLabObservation(
        profile.id,
        correcting,
        correctionReason.trim(),
        correctionFields,
        `correct:${crypto.randomUUID()}`,
      );
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: historyKey });
      setCorrecting(null);
      setCorrectionFields(null);
      setCorrectionReason("");
      toast.success("Исправление сохранено новой записью");
    },
    onError: (error) => toast.error(lifecycleError(error)),
  });

  const voidMutation = useMutation({
    mutationFn: () => {
      if (!profile || !voiding) throw new Error("Void context unavailable");
      return voidLabObservation(profile.id, voiding, voidReason.trim());
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: historyKey });
      setVoiding(null);
      setVoidReason("");
      toast.success("Запись убрана из активных");
    },
    onError: (error) => toast.error(lifecycleError(error)),
  });

  const eraseMutation = useMutation({
    mutationFn: () => {
      if (!profile || !erasing) throw new Error("Erasure context unavailable");
      return eraseLabObservation(profile.id, erasing);
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: historyKey });
      setErasing(null);
      setEraseText("");
      toast.success(
        `Удалено записей в связанной цепочке: ${result.deleted_observation_count}`,
      );
    },
    onError: (error) => toast.error(lifecycleError(error)),
  });

  const startCorrection = (observation: LabObservation) => {
    setCorrectionFields(fieldsFromObservation(observation));
    setCorrectionReason("");
    setCorrecting(observation);
    setVoiding(null);
    setErasing(null);
  };

  if (profilesQuery.isLoading || historyQuery.isLoading) {
    return (
      <div className="hm-card p-5 text-sm text-muted-foreground">Загрузка…</div>
    );
  }

  if (!profile || historyQuery.isError) {
    return (
      <div className="space-y-4">
        <Link
          to="/app/documents"
          className="inline-flex items-center gap-2 text-sm text-primary"
        >
          <ArrowLeft className="h-4 w-4" /> Назад
        </Link>
        <div className="hm-card p-5 text-sm text-destructive">
          История подтверждённых показателей недоступна. Для неё требуется право
          владельца или редактирования профиля.
        </div>
      </div>
    );
  }

  const canSubmitCorrection = Boolean(
    correctionFields &&
      correctionReason.trim() &&
      correctionFields.source_analyte_text.trim() &&
      correctionFields.source_value_text.trim() &&
      (correctionFields.value_kind !== "numeric" ||
        correctionFields.numeric_value?.toString().trim()),
  );

  return (
    <div className="space-y-6">
      <Link
        to="/app/documents"
        className="inline-flex items-center gap-2 text-sm text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> К анализам
      </Link>

      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">
          Подтверждённые показатели
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Активные записи используются в показателях и будущей динамике.
          Исправление всегда создаёт новую запись и сохраняет предыдущую в
          истории. Значение подтверждённой записи не меняется задним числом.
        </p>
      </header>

      <section className="hm-card flex flex-wrap items-center gap-4 p-5 text-sm">
        <div className="flex items-center gap-2">
          <Beaker className="h-5 w-5 text-primary" />
          <span className="font-medium">Активных: {activeCount}</span>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <History className="h-4 w-4" />
          В истории: {observations.length}
        </div>
      </section>

      {observations.length === 0 ? (
        <section className="hm-card p-6 text-sm text-muted-foreground">
          Подтверждённых показателей пока нет. Они появятся только после вашей
          отдельной проверки и подтверждения лабораторного черновика.
        </section>
      ) : (
        <section className="space-y-4">
          {observations.map((observation) => (
            <article key={observation.id} className="hm-card p-5 md:p-6">
              <div className="flex flex-col justify-between gap-4 md:flex-row">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-display text-lg font-semibold">
                      {observation.source_analyte_text}
                    </h2>
                    <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                      {labObservationStatusLabel(observation.status)}
                    </span>
                  </div>
                  <p className="mt-2 text-xl font-medium">
                    {valueDisplay(observation)}
                  </p>
                  <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm md:grid-cols-2">
                    <div>
                      <dt className="text-muted-foreground">Дата источника</dt>
                      <dd>{observation.source_observed_at_text ?? "Не указана"}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Подтверждено</dt>
                      <dd>{formatTimestamp(observation.confirmed_at)}</dd>
                    </div>
                    {observation.correction_reason && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">
                          Причина исправления
                        </dt>
                        <dd>{observation.correction_reason}</dd>
                      </div>
                    )}
                    {observation.void_reason && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">
                          Причина исключения
                        </dt>
                        <dd>{observation.void_reason}</dd>
                      </div>
                    )}
                  </dl>
                </div>

                {observation.status === "active" && (
                  <div className="flex shrink-0 flex-wrap items-start gap-2">
                    <button
                      type="button"
                      onClick={() => startCorrection(observation)}
                      className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-border px-3 py-2 text-sm font-medium"
                    >
                      <PencilLine className="h-4 w-4" /> Исправить
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setVoiding(observation);
                        setVoidReason("");
                        setCorrecting(null);
                        setErasing(null);
                      }}
                      className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-border px-3 py-2 text-sm font-medium"
                    >
                      <Undo2 className="h-4 w-4" /> Убрать из активных
                    </button>
                    {isOwner && (
                      <button
                        type="button"
                        onClick={() => {
                          setErasing(observation);
                          setEraseText("");
                          setCorrecting(null);
                          setVoiding(null);
                        }}
                        className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-destructive/50 px-3 py-2 text-sm font-medium text-destructive"
                      >
                        <Trash2 className="h-4 w-4" /> Удалить навсегда
                      </button>
                    )}
                  </div>
                )}
              </div>
            </article>
          ))}
        </section>
      )}

      {correcting && correctionFields && (
        <section className="hm-card space-y-4 border-primary/40 p-5 md:p-6">
          <div>
            <h2 className="font-display text-xl font-semibold">
              Исправление новой записью
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Исходная запись останется в истории без изменений. Проверьте все
              поля новой версии.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1.5 block font-medium">Показатель</span>
              <input
                value={correctionFields.source_analyte_text}
                maxLength={500}
                onChange={(event) =>
                  setCorrectionFields({
                    ...correctionFields,
                    source_analyte_text: event.target.value,
                  })
                }
                className="w-full rounded-xl border border-border bg-background px-3 py-2"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1.5 block font-medium">
                Значение как в источнике
              </span>
              <input
                value={correctionFields.source_value_text}
                maxLength={500}
                onChange={(event) =>
                  setCorrectionFields({
                    ...correctionFields,
                    source_value_text: event.target.value,
                  })
                }
                className="w-full rounded-xl border border-border bg-background px-3 py-2"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1.5 block font-medium">Тип значения</span>
              <select
                value={correctionFields.value_kind}
                onChange={(event) => {
                  const valueKind = event.target.value as LabValueKind;
                  setCorrectionFields({
                    ...correctionFields,
                    value_kind: valueKind,
                    numeric_value:
                      valueKind === "numeric"
                        ? correctionFields.numeric_value ?? ""
                        : null,
                    text_value:
                      valueKind === "text"
                        ? correctionFields.text_value ?? ""
                        : null,
                    qualitative_value_text:
                      valueKind === "qualitative"
                        ? correctionFields.qualitative_value_text ?? ""
                        : null,
                    comparator:
                      valueKind === "numeric"
                        ? correctionFields.comparator ?? null
                        : null,
                  });
                }}
                className="w-full rounded-xl border border-border bg-background px-3 py-2"
              >
                <option value="numeric">Число</option>
                <option value="text">Текст</option>
                <option value="qualitative">Качественный результат</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1.5 block font-medium">
                Структурированное значение
              </span>
              <input
                value={
                  correctionFields.value_kind === "numeric"
                    ? correctionFields.numeric_value?.toString() ?? ""
                    : correctionFields.value_kind === "text"
                      ? correctionFields.text_value ?? ""
                      : correctionFields.qualitative_value_text ?? ""
                }
                onChange={(event) => {
                  const value = event.target.value;
                  if (correctionFields.value_kind === "numeric") {
                    setCorrectionFields({
                      ...correctionFields,
                      numeric_value: value,
                    });
                  } else if (correctionFields.value_kind === "text") {
                    setCorrectionFields({ ...correctionFields, text_value: value });
                  } else {
                    setCorrectionFields({
                      ...correctionFields,
                      qualitative_value_text: value,
                    });
                  }
                }}
                className="w-full rounded-xl border border-border bg-background px-3 py-2"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1.5 block font-medium">Единица</span>
              <input
                value={correctionFields.source_unit_text ?? ""}
                disabled={correctionFields.unit_not_present}
                maxLength={200}
                onChange={(event) =>
                  setCorrectionFields({
                    ...correctionFields,
                    source_unit_text: event.target.value,
                  })
                }
                className="w-full rounded-xl border border-border bg-background px-3 py-2 disabled:opacity-50"
              />
              <span className="mt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={correctionFields.unit_not_present}
                  onChange={(event) =>
                    setCorrectionFields({
                      ...correctionFields,
                      unit_not_present: event.target.checked,
                      source_unit_text: event.target.checked
                        ? null
                        : correctionFields.source_unit_text ?? "",
                    })
                  }
                />
                В источнике не указана
              </span>
            </label>
            <label className="text-sm">
              <span className="mb-1.5 block font-medium">
                Референсный диапазон
              </span>
              <input
                value={correctionFields.source_reference_range_text ?? ""}
                disabled={correctionFields.reference_range_not_present}
                maxLength={500}
                onChange={(event) =>
                  setCorrectionFields({
                    ...correctionFields,
                    source_reference_range_text: event.target.value,
                  })
                }
                className="w-full rounded-xl border border-border bg-background px-3 py-2 disabled:opacity-50"
              />
              <span className="mt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={correctionFields.reference_range_not_present}
                  onChange={(event) =>
                    setCorrectionFields({
                      ...correctionFields,
                      reference_range_not_present: event.target.checked,
                      source_reference_range_text: event.target.checked
                        ? null
                        : correctionFields.source_reference_range_text ?? "",
                    })
                  }
                />
                В источнике не указан
              </span>
            </label>
          </div>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Причина исправления
            </span>
            <textarea
              value={correctionReason}
              onChange={(event) => setCorrectionReason(event.target.value)}
              maxLength={1000}
              rows={3}
              className="w-full rounded-xl border border-border bg-background px-3 py-2"
              placeholder="Например: исправлена опечатка при переносе значения"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!canSubmitCorrection || correctionMutation.isPending}
              onClick={() => correctionMutation.mutate()}
              className="min-h-11 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {correctionMutation.isPending
                ? "Сохранение…"
                : "Создать исправленную запись"}
            </button>
            <button
              type="button"
              onClick={() => {
                setCorrecting(null);
                setCorrectionFields(null);
              }}
              className="min-h-11 rounded-xl border border-border px-4 py-2 text-sm"
            >
              Отмена
            </button>
          </div>
        </section>
      )}

      {voiding && (
        <section className="hm-card space-y-4 border-amber-500/40 p-5 md:p-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-600" />
            <div>
              <h2 className="font-display text-xl font-semibold">
                Убрать запись из активных
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Запись перестанет использоваться в показателях и динамике, но
                останется в защищённой истории.
              </p>
            </div>
          </div>
          <textarea
            value={voidReason}
            onChange={(event) => setVoidReason(event.target.value)}
            maxLength={1000}
            rows={3}
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
            placeholder="Почему запись больше не должна считаться актуальной"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!voidReason.trim() || voidMutation.isPending}
              onClick={() => voidMutation.mutate()}
              className="min-h-11 rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {voidMutation.isPending ? "Сохранение…" : "Убрать из активных"}
            </button>
            <button
              type="button"
              onClick={() => setVoiding(null)}
              className="min-h-11 rounded-xl border border-border px-4 py-2 text-sm"
            >
              Отмена
            </button>
          </div>
        </section>
      )}

      {erasing && isOwner && (
        <section className="hm-card space-y-4 border-destructive/50 p-5 md:p-6">
          <div className="flex items-start gap-3">
            <Trash2 className="mt-0.5 h-5 w-5 text-destructive" />
            <div>
              <h2 className="font-display text-xl font-semibold text-destructive">
                Удалить навсегда
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Будет удалена вся связанная цепочка исходной записи и её
                исправлений вместе с лабораторными черновиками и снимками
                источника. Отменить действие нельзя.
              </p>
            </div>
          </div>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Введите УДАЛИТЬ для подтверждения
            </span>
            <input
              value={eraseText}
              onChange={(event) => setEraseText(event.target.value)}
              autoComplete="off"
              className="w-full rounded-xl border border-destructive/50 bg-background px-3 py-2"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={eraseText !== "УДАЛИТЬ" || eraseMutation.isPending}
              onClick={() => eraseMutation.mutate()}
              className="min-h-11 rounded-xl bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground disabled:opacity-50"
            >
              {eraseMutation.isPending ? "Удаление…" : "Удалить навсегда"}
            </button>
            <button
              type="button"
              onClick={() => setErasing(null)}
              className="min-h-11 rounded-xl border border-border px-4 py-2 text-sm"
            >
              Отмена
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
