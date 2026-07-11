import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronDown, HelpCircle, Loader2, Pencil, Plus, ShieldAlert } from "lucide-react";

import {
  ClinicalClarifyingQuestions,
  type ClinicalAnswers,
} from "@/components/ClinicalClarifyingQuestions";
import { ClinicalRecordActions } from "@/components/ClinicalRecordActions";
import { ClinicalTypeahead, type ClinicalSelection } from "@/components/ClinicalTypeahead";
import {
  ApiError,
  apiGet,
  apiPatch,
  apiPost,
  type ClinicalContextSummary,
  type ClinicalReviewState,
  type ClinicalSectionState,
} from "@/lib/api";
import { formatDateOnlyRu, localDateOnlyISO } from "@/lib/utils";

export type SectionKey = "conditions" | "allergies" | "medications" | "supplements";

export type ClinicalRecord = {
  id: string;
  display_name?: string;
  substance_name?: string;
  clinical_status?: string;
  status?: string;
  reaction?: string | null;
  severity?: string | null;
  dose_value?: string | number | null;
  dose_unit?: string | null;
  frequency_text?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  reason_text?: string | null;
  updated_at: string;
};

const SECTIONS: Array<{
  key: SectionKey;
  title: string;
  emptyLabel: string;
  placeholder: string;
}> = [
  { key: "conditions", title: "Состояния и симптомы", emptyLabel: "состояний и симптомов нет", placeholder: "Например, головная боль" },
  {
    key: "allergies",
    title: "Аллергии и непереносимости",
    emptyLabel: "аллергий и непереносимостей нет",
    placeholder: "Например, пенициллин или арахис",
  },
  { key: "medications", title: "Лекарства", emptyLabel: "лекарств нет", placeholder: "Название лекарства" },
  { key: "supplements", title: "Добавки", emptyLabel: "добавок нет", placeholder: "Например, магний" },
];

async function loadClinicalContext(profileId: string) {
  const [summary, conditions, allergies, medications, supplements] = await Promise.all([
    apiGet<ClinicalContextSummary>(`/profiles/${profileId}/clinical-context/state`),
    apiGet<ClinicalRecord[]>(`/profiles/${profileId}/conditions`),
    apiGet<ClinicalRecord[]>(`/profiles/${profileId}/allergies`),
    apiGet<ClinicalRecord[]>(`/profiles/${profileId}/medications`),
    apiGet<ClinicalRecord[]>(`/profiles/${profileId}/supplements`),
  ]);
  return { summary, conditions, allergies, medications, supplements };
}

export function createClinicalPayload(
  section: SectionKey,
  input: string | ClinicalSelection,
  answers: ClinicalAnswers = {},
) {
  const selection: ClinicalSelection = typeof input === "string"
    ? { displayText: input, canonicalConceptId: null, source: "free_text" }
    : input;
  const provenance = selection.canonicalConceptId
    ? { code_system: "health_compass", code: selection.canonicalConceptId }
    : {};
  const dose = answers.doseValue && answers.doseUnit
    ? { dose_value: Number(answers.doseValue), dose_unit: answers.doseUnit.trim() }
    : {};

  if (section === "conditions") {
    const status = answers.presencePattern === "resolved"
      ? "resolved"
      : answers.presencePattern === "unknown"
        ? "unknown"
        : "active";
    return {
      display_name: selection.displayText,
      clinical_status: status,
      ...(answers.onsetTiming ? { onset_timing: answers.onsetTiming } : {}),
      ...(answers.presencePattern ? { presence_pattern: answers.presencePattern } : {}),
      ...provenance,
    };
  }
  if (section === "allergies") {
    const status = answers.currentUse === "no" ? "inactive" : answers.currentUse === "unknown" ? "unknown" : "active";
    return {
      substance_name: selection.displayText,
      allergy_type: "unknown",
      clinical_status: status,
      ...(answers.reaction?.trim() ? { reaction: answers.reaction.trim() } : {}),
      ...(answers.severity ? { severity: answers.severity } : {}),
      ...provenance,
    };
  }
  if (section === "medications") {
    const status = answers.currentUse === "no" ? "completed" : answers.currentUse === "unknown" ? "unknown" : "active";
    return {
      display_name: selection.displayText,
      status,
      ...(answers.startDate ? { start_date: answers.startDate } : {}),
      ...(answers.frequencyText?.trim() ? { frequency_text: answers.frequencyText.trim() } : {}),
      ...(answers.reasonText?.trim() ? { reason_text: answers.reasonText.trim() } : {}),
      ...dose,
      ...provenance,
    };
  }
  const status = answers.currentUse === "no" ? "completed" : answers.currentUse === "unknown" ? "unknown" : "active";
  return {
    display_name: selection.displayText,
    supplement_type: "unknown",
    status,
    ...(answers.startDate ? { start_date: answers.startDate } : {}),
    ...(answers.frequencyText?.trim() ? { frequency_text: answers.frequencyText.trim() } : {}),
    ...dose,
    ...provenance,
  };
}

export function clinicalRecordLabel(record: ClinicalRecord) {
  return record.display_name ?? record.substance_name ?? "Запись";
}

export function isClinicalRecordActive(section: SectionKey, record: ClinicalRecord) {
  if (section === "conditions" || section === "allergies") return record.clinical_status === "active";
  return record.status === "active";
}

export function clinicalSectionStatusLabel(state: ClinicalSectionState) {
  if (state.effective_state === "confirmed_none") return "Подтверждено отсутствие";
  if (state.effective_state === "deferred") return "Можно заполнить позже";
  if (state.effective_state === "has_entries") {
    return state.active_count > 0 ? `Активных записей: ${state.active_count}` : "Есть история";
  }
  return "Пока не заполнено";
}

export function clinicalEmptyActionLabel(emptyLabel: string) {
  return `Подтвердить: ${emptyLabel}`;
}

export function clinicalErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    let message = error.message;
    if (error.status === 409) {
      message = "Данные изменились в другом окне или на другом устройстве. Обновите страницу и повторите действие.";
    }
    return error.requestId ? `${message} (код запроса: ${error.requestId})` : message;
  }
  return error instanceof Error ? error.message : "Не удалось сохранить изменения.";
}

export type RecordEditorFields = {
  name: string;
  frequency: string;
  doseValue: string;
  doseUnit: string;
};

export function recordEditorInitialState(record: ClinicalRecord): RecordEditorFields {
  return {
    name: clinicalRecordLabel(record),
    frequency: record.frequency_text ?? "",
    doseValue: record.dose_value == null ? "" : String(record.dose_value),
    doseUnit: record.dose_unit ?? "",
  };
}

/**
 * Build the PATCH payload for the record editor. Clearing both dose fields
 * explicitly sends nulls so an existing dose can actually be removed;
 * a half-filled dose pair is a validation error, never silently dropped.
 */
export function buildRecordPatchPayload(
  section: SectionKey,
  fields: RecordEditorFields,
): { payload: Record<string, unknown> } | { validationError: string } {
  const name = fields.name.trim();
  if (!name) return { validationError: "Название не может быть пустым." };
  const payload: Record<string, unknown> = section === "allergies"
    ? { substance_name: name }
    : { display_name: name };
  if (section === "medications" || section === "supplements") {
    payload.frequency_text = fields.frequency.trim() || null;
    const doseValue = fields.doseValue.trim();
    const doseUnit = fields.doseUnit.trim();
    if (doseValue && doseUnit) {
      const numericDose = Number(doseValue.replace(",", "."));
      if (!Number.isFinite(numericDose) || numericDose <= 0) {
        return { validationError: "Доза должна быть положительным числом." };
      }
      payload.dose_value = numericDose;
      payload.dose_unit = doseUnit;
    } else if (!doseValue && !doseUnit) {
      payload.dose_value = null;
      payload.dose_unit = null;
    } else {
      return { validationError: "Укажите и дозу, и единицу измерения — или очистите оба поля." };
    }
  }
  return { payload };
}

export function WhyWeAsk() {
  return (
    <details className="mt-3 rounded-xl border border-border/70 bg-muted/20 px-3 py-2 text-sm">
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <HelpCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
        Зачем это нужно
      </summary>
      <p className="pb-2 pt-1 leading-5 text-muted-foreground">
        Эти сведения помогают Health Compass учитывать ваш контекст при анализе данных, отчётах и рекомендациях.
        Раздел можно не заполнять: все основные функции продолжат работать, но ответы могут быть менее персонализированными.
      </p>
    </details>
  );
}

function RecordEditor({
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
  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState<RecordEditorFields>(() => recordEditorInitialState(record));
  const [validationError, setValidationError] = useState<string | null>(null);
  const { name, frequency, doseValue, doseUnit } = fields;
  const setField = (key: keyof RecordEditorFields) => (value: string) =>
    setFields((current) => ({ ...current, [key]: value }));

  const startEditing = () => {
    setFields(recordEditorInitialState(record));
    setValidationError(null);
    setEditing(true);
  };

  const mutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiPatch(`/profiles/${profileId}/${section}/${record.id}`, {
        ...payload,
        expected_updated_at: record.updated_at,
      }),
    onSuccess: () => {
      setEditing(false);
      onSaved();
    },
  });

  const completeCourse = () => {
    if (section !== "medications" && section !== "supplements") return;
    mutation.mutate({ status: "completed", end_date: localDateOnlyISO() });
  };

  if (editing) {
    return (
      <form
        className="space-y-2 rounded-xl border border-border bg-background p-3"
        onSubmit={(event) => {
          event.preventDefault();
          const result = buildRecordPatchPayload(section, fields);
          if ("validationError" in result) {
            setValidationError(result.validationError);
            return;
          }
          setValidationError(null);
          mutation.mutate(result.payload);
        }}
      >
        <input value={name} onChange={(event) => setField("name")(event.target.value)} className="min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2" />
        {(section === "medications" || section === "supplements") && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <input value={doseValue} inputMode="decimal" onChange={(event) => setField("doseValue")(event.target.value)} placeholder="Доза" className="min-h-11 rounded-xl border border-border bg-background px-3 py-2" />
              <input value={doseUnit} onChange={(event) => setField("doseUnit")(event.target.value)} placeholder="мг, мл" className="min-h-11 rounded-xl border border-border bg-background px-3 py-2" />
            </div>
            <input value={frequency} onChange={(event) => setField("frequency")(event.target.value)} placeholder="Как часто" className="min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2" />
          </>
        )}
        <div className="grid grid-cols-2 gap-2">
          <button type="submit" disabled={!name.trim() || mutation.isPending} className="min-h-10 rounded-xl bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50">Сохранить</button>
          <button type="button" onClick={() => setEditing(false)} className="min-h-10 rounded-xl border border-border px-3 py-2 text-sm">Отмена</button>
        </div>
        {validationError && <p className="text-xs text-destructive" role="alert">{validationError}</p>}
        {mutation.error && <p className="text-xs text-destructive" role="alert">{clinicalErrorMessage(mutation.error)}</p>}
      </form>
    );
  }

  return (
    <div className="rounded-xl bg-muted/40 px-3 py-2.5 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="break-words font-medium">{clinicalRecordLabel(record)}</div>
          {(record.dose_value || record.frequency_text) && (
            <p className="mt-1 text-xs text-muted-foreground">
              {record.dose_value ? `${record.dose_value} ${record.dose_unit ?? ""}`.trim() : ""}
              {record.dose_value && record.frequency_text ? " · " : ""}
              {record.frequency_text ?? ""}
            </p>
          )}
          {record.end_date && <p className="mt-1 text-xs text-muted-foreground">Завершено: {formatDateOnlyRu(record.end_date)}</p>}
        </div>
        <button type="button" onClick={startEditing} className="rounded-lg p-2 text-muted-foreground hover:bg-muted" aria-label={`Редактировать ${clinicalRecordLabel(record)}`}>
          <Pencil className="h-4 w-4" />
        </button>
      </div>
      {isClinicalRecordActive(section, record) && (section === "medications" || section === "supplements") && (
        <button type="button" disabled={mutation.isPending} onClick={completeCourse} className="mt-2 text-xs font-medium text-primary disabled:opacity-50">
          Завершить курс
        </button>
      )}
      <ClinicalRecordActions
        profileId={profileId}
        section={section}
        record={record}
        onSaved={onSaved}
      />
      {mutation.error && (
        <p className="mt-2 text-xs text-destructive" role="alert">{clinicalErrorMessage(mutation.error)}</p>
      )}
    </div>
  );
}

export function ClinicalContextSection({ profileId, consentActive }: { profileId: string; consentActive: boolean }) {
  const queryClient = useQueryClient();
  const [editingSection, setEditingSection] = useState<SectionKey | null>(null);
  const [selection, setSelection] = useState<ClinicalSelection | null>(null);
  const [answers, setAnswers] = useState<ClinicalAnswers>({});
  const queryKey = useMemo(() => ["clinical-context", profileId], [profileId]);
  const { data, isLoading, error } = useQuery({ queryKey, queryFn: () => loadClinicalContext(profileId) });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey });
    queryClient.invalidateQueries({ queryKey: ["profile-completion", profileId] });
  };
  const resetEditor = () => {
    setEditingSection(null);
    setSelection(null);
    setAnswers({});
  };

  const addMutation = useMutation({
    mutationFn: ({ section, selected, details }: { section: SectionKey; selected: ClinicalSelection; details: ClinicalAnswers }) =>
      apiPost(`/profiles/${profileId}/${section}`, createClinicalPayload(section, selected, details)),
    onSuccess: () => {
      resetEditor();
      invalidate();
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({ section, reviewState, updatedAt }: { section: SectionKey; reviewState: ClinicalReviewState; updatedAt: string | null }) =>
      apiPatch(`/profiles/${profileId}/clinical-context/sections/${section}/review`, {
        review_state: reviewState,
        expected_updated_at: updatedAt,
      }),
    onSuccess: invalidate,
  });

  if (isLoading) {
    return (
      <section className="hm-card grid min-h-40 place-items-center p-5" aria-label="Загрузка клинического контекста">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
      </section>
    );
  }

  if (error || !data) {
    return <section className="hm-card p-5 text-sm text-destructive" role="alert">Не удалось загрузить клинический контекст.</section>;
  }

  return (
    <section className="hm-card p-4 sm:p-5 md:p-6">
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        <div>
          <h2 className="font-display text-lg font-semibold">Клинический контекст</h2>
          <p className="mt-1 text-sm leading-5 text-muted-foreground">Укажите только то, что вы знаете. Заполнить эти сведения можно позже.</p>
        </div>
      </div>
      <WhyWeAsk />

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {SECTIONS.map((section) => {
          const state = data.summary.sections[section.key];
          const records = data[section.key];
          const activeRecords = records.filter((record) => isClinicalRecordActive(section.key, record));
          const historyRecords = records.filter((record) => !isClinicalRecordActive(section.key, record));
          const isEditing = editingSection === section.key;
          const isBusy = addMutation.isPending || reviewMutation.isPending;
          const isConfirmedNone = state.effective_state === "confirmed_none";
          return (
            <article id={`clinical-${section.key}`} key={section.key} className="scroll-mt-24 rounded-2xl border border-border/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-medium leading-5">{section.title}</h3>
                  <p className="mt-1 inline-flex rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">{clinicalSectionStatusLabel(state)}</p>
                </div>
                {isConfirmedNone && <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden="true" />}
              </div>

              {activeRecords.length > 0 && (
                <div className="mt-3 space-y-2" aria-label={`Активные записи раздела «${section.title}»`}>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Сейчас</p>
                  {activeRecords.map((record) => (
                    <RecordEditor key={record.id} profileId={profileId} section={section.key} record={record} onSaved={invalidate} />
                  ))}
                </div>
              )}

              {historyRecords.length > 0 && (
                <details className="mt-3 rounded-xl border border-border/60 px-3 py-2">
                  <summary className="flex min-h-9 cursor-pointer list-none items-center justify-between text-sm font-medium">
                    История · {historyRecords.length}
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  </summary>
                  <div className="mt-2 space-y-2">
                    {historyRecords.map((record) => (
                      <RecordEditor key={record.id} profileId={profileId} section={section.key} record={record} onSaved={invalidate} />
                    ))}
                  </div>
                </details>
              )}

              {isEditing && (
                <form className="mt-3 space-y-3" onSubmit={(event) => {
                  event.preventDefault();
                  if (selection && !addMutation.isPending) {
                    addMutation.mutate({ section: section.key, selected: selection, details: answers });
                  }
                }}>
                  <ClinicalTypeahead
                    profileId={profileId}
                    section={section.key}
                    placeholder={section.placeholder}
                    value={selection}
                    onChange={(next) => {
                      setSelection(next);
                      if (!next) setAnswers({});
                    }}
                  />
                  {selection && (
                    <ClinicalClarifyingQuestions
                      section={section.key}
                      answers={answers}
                      onChange={setAnswers}
                    />
                  )}
                  <div className="grid grid-cols-2 gap-2 sm:flex">
                    <button type="submit" disabled={!selection || addMutation.isPending} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
                      {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}Сохранить
                    </button>
                    <button type="button" disabled={addMutation.isPending} onClick={resetEditor} className="min-h-11 rounded-xl border border-border px-4 py-2 text-sm text-muted-foreground disabled:opacity-50">Отмена</button>
                  </div>
                </form>
              )}

              {!isEditing && (
                <div className="mt-4 grid gap-2 sm:flex sm:flex-wrap">
                  <button type="button" disabled={!consentActive || isBusy} onClick={() => { setEditingSection(section.key); setSelection(null); setAnswers({}); }} className="inline-flex min-h-11 w-full items-center justify-center gap-1.5 rounded-xl border border-border px-3 py-2 text-sm font-medium sm:w-auto disabled:opacity-50">
                    <Plus className="h-4 w-4" aria-hidden="true" /> Добавить запись
                  </button>
                  {records.length === 0 && !isConfirmedNone && (
                    <button type="button" disabled={!consentActive || isBusy} onClick={() => reviewMutation.mutate({ section: section.key, reviewState: "confirmed_none", updatedAt: state.updated_at })} className="min-h-11 w-full rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-primary sm:w-auto disabled:opacity-50">{clinicalEmptyActionLabel(section.emptyLabel)}</button>
                  )}
                  {records.length === 0 && state.effective_state !== "deferred" && (
                    <button type="button" disabled={!consentActive || isBusy} onClick={() => reviewMutation.mutate({ section: section.key, reviewState: "deferred", updatedAt: state.updated_at })} className="min-h-11 w-full rounded-xl px-3 py-2 text-sm text-muted-foreground sm:w-auto disabled:opacity-50">Не сейчас</button>
                  )}
                  {(state.effective_state === "deferred" || isConfirmedNone) && (
                    <button type="button" disabled={!consentActive || isBusy} onClick={() => reviewMutation.mutate({ section: section.key, reviewState: "unknown", updatedAt: state.updated_at })} className="min-h-11 w-full rounded-xl px-3 py-2 text-sm text-muted-foreground sm:w-auto disabled:opacity-50">Изменить решение</button>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {!consentActive && <div className="mt-4 rounded-xl border border-border bg-muted/30 px-3 py-3 text-sm text-muted-foreground">Чтобы добавлять медицинские сведения, сначала примите согласие на обработку данных здоровья выше на странице. Удаление своих ранее внесённых записей остаётся доступным.</div>}
      {(addMutation.error || reviewMutation.error) && <p className="mt-3 text-sm text-destructive" role="alert">{clinicalErrorMessage(addMutation.error ?? reviewMutation.error)}</p>}
      {(addMutation.isPending || reviewMutation.isPending) && <span className="sr-only" aria-live="polite">Сохраняем изменения</span>}
    </section>
  );
}
