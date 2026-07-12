import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Beaker, CheckCircle2, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ApiError, apiGet, type HealthProfile } from "@/lib/api";
import {
  createLabDraft,
  getLabDraftContext,
  labDraftStatusLabel,
  listLabDrafts,
  setLabDraftSources,
  setLabDraftStatus,
  type LabDraft,
  type LabDraftFields,
  type LabValueKind,
} from "@/lib/labDraftApi";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return "Исходный документ или проверенный текст изменились. Обновите страницу.";
    }
    if (error.status === 422) return "Проверьте заполненные поля.";
    if (error.status === 428) {
      return "Не хватает версии данных для безопасного сохранения.";
    }
    return error.message;
  }
  return "Не удалось сохранить лабораторный черновик.";
}

export default function LabDrafts() {
  const { documentId } = useParams<{ documentId: string }>();
  const queryClient = useQueryClient();
  const [analyteText, setAnalyteText] = useState("");
  const [valueText, setValueText] = useState("");
  const [valueKind, setValueKind] = useState<LabValueKind>("numeric");
  const [numericValue, setNumericValue] = useState("");
  const [textValue, setTextValue] = useState("");
  const [unitText, setUnitText] = useState("");
  const [unitMissing, setUnitMissing] = useState(false);
  const [rangeText, setRangeText] = useState("");
  const [rangeMissing, setRangeMissing] = useState(true);
  const [observedText, setObservedText] = useState("");
  const [observedUnknown, setObservedUnknown] = useState(true);
  const [observedDate, setObservedDate] = useState("");
  const [analyteCandidateId, setAnalyteCandidateId] = useState("");
  const [valueCandidateId, setValueCandidateId] = useState("");

  const profilesQuery = useQuery({
    queryKey: ["health-profiles", "lab-drafts"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
  });
  const profile = profilesQuery.data?.[0] ?? null;
  const contextKey = ["lab-draft-context", profile?.id, documentId] as const;
  const draftsKey = ["lab-drafts", profile?.id, documentId] as const;

  const contextQuery = useQuery({
    queryKey: contextKey,
    queryFn: () => getLabDraftContext(profile!.id, documentId!),
    enabled: Boolean(profile && documentId),
  });
  const draftsQuery = useQuery({
    queryKey: draftsKey,
    queryFn: () => listLabDrafts(profile!.id, documentId!),
    enabled: Boolean(profile && documentId),
  });
  const context = contextQuery.data;
  const candidates = context?.candidates ?? [];
  const candidateById = useMemo(
    () => new Map(candidates.map((candidate) => [candidate.id, candidate])),
    [candidates],
  );

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!profile || !documentId || !context) {
        throw new Error("Context unavailable");
      }
      const fields: LabDraftFields = {
        source_analyte_text: analyteText.trim(),
        source_value_text: valueText.trim(),
        value_kind: valueKind,
        numeric_value: valueKind === "numeric" ? numericValue.trim() : null,
        text_value: valueKind === "text" ? textValue.trim() : null,
        qualitative_value_text:
          valueKind === "qualitative" ? textValue.trim() : null,
        source_unit_text: unitMissing ? null : unitText.trim(),
        unit_not_present: unitMissing,
        source_reference_range_text: rangeMissing ? null : rangeText.trim(),
        reference_range_not_present: rangeMissing,
        source_observed_at_text: observedUnknown ? null : observedText.trim(),
        observed_time_unknown: observedUnknown,
        observed_date: observedUnknown ? null : observedDate,
        observed_at: null,
        observed_precision: observedUnknown ? "unknown" : "date",
      };
      const draft = await createLabDraft(
        profile.id,
        documentId,
        context,
        fields,
      );
      const analyteCandidate = candidateById.get(analyteCandidateId);
      const valueCandidate = candidateById.get(valueCandidateId);
      if (!analyteCandidate || !valueCandidate) {
        throw new Error("Source candidates are required");
      }
      return setLabDraftSources(profile.id, documentId, context, draft, [
        {
          candidate_id: analyteCandidate.id,
          source_role: "analyte",
          expected_updated_at: analyteCandidate.updated_at,
        },
        {
          candidate_id: valueCandidate.id,
          source_role: "value",
          expected_updated_at: valueCandidate.updated_at,
        },
      ]);
    },
    onSuccess: (draft) => {
      queryClient.setQueryData<LabDraft[]>(draftsKey, (current = []) => [
        ...current,
        draft,
      ]);
      toast.success("Лабораторный черновик сохранён");
      setAnalyteText("");
      setValueText("");
      setNumericValue("");
      setTextValue("");
      setAnalyteCandidateId("");
      setValueCandidateId("");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const readyMutation = useMutation({
    mutationFn: (draft: LabDraft) =>
      setLabDraftStatus(profile!.id, documentId!, context!, draft, "ready"),
    onSuccess: (next) => {
      queryClient.setQueryData<LabDraft[]>(draftsKey, (current = []) =>
        current.map((draft) => (draft.id === next.id ? next : draft)),
      );
      toast.success("Черновик готов к отдельному подтверждению");
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  if (
    profilesQuery.isLoading ||
    contextQuery.isLoading ||
    draftsQuery.isLoading
  ) {
    return (
      <div className="hm-card p-5 text-sm text-muted-foreground">Загрузка…</div>
    );
  }
  if (!profile || !documentId || contextQuery.isError || !context) {
    return (
      <div className="space-y-4">
        <Link
          to="/app/documents"
          className="inline-flex items-center gap-2 text-sm text-primary"
        >
          <ArrowLeft className="h-4 w-4" /> Назад к документам
        </Link>
        <div className="hm-card p-5 text-sm text-destructive">
          Лабораторные черновики доступны только после завершённой проверки OCR
          и решения о пациенте.
        </div>
      </div>
    );
  }

  const canCreate =
    analyteText.trim().length > 0 &&
    valueText.trim().length > 0 &&
    analyteCandidateId.length > 0 &&
    valueCandidateId.length > 0 &&
    (valueKind === "numeric"
      ? numericValue.trim().length > 0
      : textValue.trim().length > 0) &&
    (unitMissing || unitText.trim().length > 0) &&
    (rangeMissing || rangeText.trim().length > 0) &&
    (observedUnknown ||
      (observedText.trim().length > 0 && observedDate.length > 0));

  return (
    <div className="space-y-6">
      <Link
        to={`/app/documents/${documentId}/review`}
        className="inline-flex items-center gap-2 text-sm text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> Назад к проверенному тексту
      </Link>

      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">
          Лабораторные черновики
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Структурируйте только то, что явно указано в документе. Черновик не
          является подтверждённым показателем и не используется в динамике или
          AI-анализе.
        </p>
      </header>

      <section className="hm-card p-5 md:p-6">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div>
            <h2 className="font-display text-lg font-semibold">
              Источник зафиксирован
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              OCR-проверка завершена. Решение о пациенте:{" "}
              {context.patient_decision === "match"
                ? "совпадает с профилем"
                : "имя пациента не указано"}
              .
            </p>
          </div>
        </div>
      </section>

      <section className="hm-card space-y-4 p-5 md:p-6">
        <div className="flex items-center gap-2">
          <Beaker className="h-5 w-5 text-primary" />
          <h2 className="font-display text-lg font-semibold">Новый черновик</h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Фрагмент с названием показателя
            </span>
            <select
              value={analyteCandidateId}
              onChange={(event) => {
                setAnalyteCandidateId(event.target.value);
                const candidate = candidateById.get(event.target.value);
                if (candidate) {
                  setAnalyteText(
                    candidate.reviewed_text ?? candidate.original_text,
                  );
                }
              }}
              className="w-full rounded-xl border border-border bg-background px-3 py-2"
            >
              <option value="">Выберите фрагмент</option>
              {candidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  Стр. {candidate.page_number}:{" "}
                  {candidate.reviewed_text ?? candidate.original_text}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Название как в источнике
            </span>
            <input
              value={analyteText}
              onChange={(event) => setAnalyteText(event.target.value)}
              maxLength={500}
              className="w-full rounded-xl border border-border bg-background px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Фрагмент со значением
            </span>
            <select
              value={valueCandidateId}
              onChange={(event) => {
                setValueCandidateId(event.target.value);
                const candidate = candidateById.get(event.target.value);
                if (candidate) {
                  setValueText(
                    candidate.reviewed_text ?? candidate.original_text,
                  );
                }
              }}
              className="w-full rounded-xl border border-border bg-background px-3 py-2"
            >
              <option value="">Выберите фрагмент</option>
              {candidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  Стр. {candidate.page_number}:{" "}
                  {candidate.reviewed_text ?? candidate.original_text}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Значение как в источнике
            </span>
            <input
              value={valueText}
              onChange={(event) => setValueText(event.target.value)}
              maxLength={500}
              className="w-full rounded-xl border border-border bg-background px-3 py-2"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">Тип значения</span>
            <select
              value={valueKind}
              onChange={(event) =>
                setValueKind(event.target.value as LabValueKind)
              }
              className="w-full rounded-xl border border-border bg-background px-3 py-2"
            >
              <option value="numeric">Число</option>
              <option value="text">Текст</option>
              <option value="qualitative">Качественный результат</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              {valueKind === "numeric"
                ? "Числовое значение"
                : "Проверенное представление"}
            </span>
            <input
              value={valueKind === "numeric" ? numericValue : textValue}
              onChange={(event) =>
                valueKind === "numeric"
                  ? setNumericValue(event.target.value)
                  : setTextValue(event.target.value)
              }
              className="w-full rounded-xl border border-border bg-background px-3 py-2"
            />
          </label>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Единица как в источнике
            </span>
            <input
              value={unitText}
              onChange={(event) => setUnitText(event.target.value)}
              disabled={unitMissing}
              className="w-full rounded-xl border border-border bg-background px-3 py-2 disabled:opacity-60"
            />
            <span className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={unitMissing}
                onChange={(event) => setUnitMissing(event.target.checked)}
              />{" "}
              В документе единица не указана
            </span>
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Референсный диапазон
            </span>
            <input
              value={rangeText}
              onChange={(event) => setRangeText(event.target.value)}
              disabled={rangeMissing}
              className="w-full rounded-xl border border-border bg-background px-3 py-2 disabled:opacity-60"
            />
            <span className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={rangeMissing}
                onChange={(event) => setRangeMissing(event.target.checked)}
              />{" "}
              В документе диапазон не указан
            </span>
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block font-medium">
              Дата как в источнике
            </span>
            <input
              value={observedText}
              onChange={(event) => setObservedText(event.target.value)}
              disabled={observedUnknown}
              className="w-full rounded-xl border border-border bg-background px-3 py-2 disabled:opacity-60"
            />
            {!observedUnknown && (
              <input
                type="date"
                value={observedDate}
                onChange={(event) => setObservedDate(event.target.value)}
                className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2"
              />
            )}
            <span className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={observedUnknown}
                onChange={(event) => setObservedUnknown(event.target.checked)}
              />{" "}
              Дата в документе не указана
            </span>
          </label>
        </div>

        <button
          type="button"
          disabled={!canCreate || createMutation.isPending}
          onClick={() => createMutation.mutate()}
          className="inline-flex min-h-11 items-center justify-center rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {createMutation.isPending ? "Сохраняется…" : "Сохранить черновик"}
        </button>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-xl font-semibold">
          Сохранённые черновики
        </h2>
        {(draftsQuery.data ?? []).length === 0 ? (
          <div className="hm-card p-5 text-sm text-muted-foreground">
            Черновиков пока нет.
          </div>
        ) : (
          (draftsQuery.data ?? []).map((draft) => (
            <article key={draft.id} className="hm-card p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-display text-lg font-semibold">
                    {draft.source_analyte_text}
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {draft.source_value_text}
                    {draft.source_unit_text ? ` ${draft.source_unit_text}` : ""}
                  </p>
                </div>
                <span className="rounded-full border border-border px-2.5 py-1 text-xs font-medium">
                  {labDraftStatusLabel(draft.status)}
                </span>
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Источников: {draft.sources.length}. Обновлено{" "}
                {new Date(draft.updated_at).toLocaleString("ru-RU")}.
              </p>
              {draft.status === "draft" && (
                <button
                  type="button"
                  disabled={readyMutation.isPending}
                  onClick={() => readyMutation.mutate(draft)}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl border border-success/30 bg-success/10 px-4 py-2 text-sm font-medium text-success disabled:opacity-50"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Готово к отдельному подтверждению
                </button>
              )}
              {draft.status === "ready" && (
                <Link
                  to={`/app/documents/${documentId}/labs/${draft.id}/confirm`}
                  className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Проверить и подтвердить запись
                </Link>
              )}
              {draft.status === "confirmed" &&
                draft.confirmed_observation_id && (
                  <p className="mt-4 text-sm text-success">
                    Создана неизменяемая подтверждённая запись.
                  </p>
                )}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
