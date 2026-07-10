import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Plus, ShieldAlert } from "lucide-react";

import { apiGet, apiPost, type ClinicalContextSummary, type ClinicalSectionState } from "@/lib/api";

export type SectionKey = "conditions" | "allergies" | "medications" | "supplements";

export type ClinicalRecord = {
  id: string;
  display_name?: string;
  substance_name?: string;
  clinical_status?: string;
  status?: string;
};

const SECTIONS: Array<{
  key: SectionKey;
  title: string;
  emptyLabel: string;
  placeholder: string;
}> = [
  { key: "conditions", title: "Состояния", emptyLabel: "состояний нет", placeholder: "Например, гипертония" },
  {
    key: "allergies",
    title: "Аллергии и непереносимости",
    emptyLabel: "аллергий и непереносимостей нет",
    placeholder: "Например, пенициллин или арахис",
  },
  {
    key: "medications",
    title: "Лекарства",
    emptyLabel: "постоянных лекарств нет",
    placeholder: "Название лекарства",
  },
  { key: "supplements", title: "Добавки", emptyLabel: "добавок нет", placeholder: "Например, магний" },
];

async function loadClinicalContext(profileId: string) {
  const [summary, conditions, allergies, medications, supplements] = await Promise.all([
    apiGet<ClinicalContextSummary>(`/profiles/${profileId}/clinical-context`),
    apiGet<ClinicalRecord[]>(`/profiles/${profileId}/conditions`),
    apiGet<ClinicalRecord[]>(`/profiles/${profileId}/allergies`),
    apiGet<ClinicalRecord[]>(`/profiles/${profileId}/medications`),
    apiGet<ClinicalRecord[]>(`/profiles/${profileId}/supplements`),
  ]);
  return { summary, conditions, allergies, medications, supplements };
}

export function createClinicalPayload(section: SectionKey, value: string) {
  if (section === "conditions") {
    return { display_name: value, clinical_status: "active" };
  }
  if (section === "allergies") {
    return {
      substance_name: value,
      allergy_type: "unknown",
      clinical_status: "active",
    };
  }
  if (section === "medications") {
    return { display_name: value, status: "active" };
  }
  return { display_name: value, supplement_type: "unknown", status: "active" };
}

export function clinicalRecordLabel(record: ClinicalRecord) {
  return record.display_name ?? record.substance_name ?? "Запись";
}

export function clinicalSectionStatusLabel(state: ClinicalSectionState) {
  if (state.confirmed_empty) return "Подтверждено отсутствие";
  if (state.active_count > 0) return `Активных записей: ${state.active_count}`;
  if (state.reviewed) return "Раздел просмотрен";
  return "Пока не заполнено";
}

export function clinicalEmptyActionLabel(emptyLabel: string) {
  return `Подтвердить: ${emptyLabel}`;
}

export function ClinicalContextSection({ profileId, consentActive }: { profileId: string; consentActive: boolean }) {
  const queryClient = useQueryClient();
  const [editingSection, setEditingSection] = useState<SectionKey | null>(null);
  const [value, setValue] = useState("");
  const queryKey = useMemo(() => ["clinical-context", profileId], [profileId]);
  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => loadClinicalContext(profileId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey });

  const addMutation = useMutation({
    mutationFn: ({ section, name }: { section: SectionKey; name: string }) =>
      apiPost(`/profiles/${profileId}/${section}`, createClinicalPayload(section, name)),
    onSuccess: () => {
      setEditingSection(null);
      setValue("");
      invalidate();
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({ section, confirmedEmpty }: { section: SectionKey; confirmedEmpty: boolean }) =>
      apiPost(`/profiles/${profileId}/clinical-context/review`, {
        section,
        confirmed_empty: confirmedEmpty,
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
    return (
      <section className="hm-card p-5 text-sm text-destructive" role="alert">
        Не удалось загрузить клинический контекст.
      </section>
    );
  }

  return (
    <section className="hm-card p-4 sm:p-5 md:p-6">
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        <div>
          <h2 className="font-display text-lg font-semibold">Клинический контекст</h2>
          <p className="mt-1 text-sm leading-5 text-muted-foreground">
            Укажите только то, что вы знаете. Эти сведения помогают безопаснее интерпретировать данные, а заполнить их можно позже.
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {SECTIONS.map((section) => {
          const state = data.summary.sections[section.key];
          const records = data[section.key];
          const isEditing = editingSection === section.key;
          const isBusy = addMutation.isPending || reviewMutation.isPending;
          return (
            <article key={section.key} className="rounded-2xl border border-border/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-medium leading-5">{section.title}</h3>
                  <p
                    className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs ${
                      state.confirmed_empty
                        ? "bg-success/10 text-success"
                        : state.active_count > 0
                          ? "bg-primary/10 text-primary"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {clinicalSectionStatusLabel(state)}
                  </p>
                </div>
                {state.confirmed_empty && <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden="true" />}
              </div>

              {records.length > 0 && (
                <div className="mt-3 space-y-2" aria-label={`Записи раздела «${section.title}»`}>
                  {records.slice(0, 3).map((record) => (
                    <div key={record.id} className="break-words rounded-xl bg-muted/40 px-3 py-2.5 text-sm">
                      {clinicalRecordLabel(record)}
                    </div>
                  ))}
                  {records.length > 3 && (
                    <p className="text-xs text-muted-foreground">Ещё записей: {records.length - 3}</p>
                  )}
                </div>
              )}

              {isEditing && (
                <form
                  className="mt-3 space-y-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const name = value.trim();
                    if (name && !addMutation.isPending) addMutation.mutate({ section: section.key, name });
                  }}
                >
                  <label className="block text-xs font-medium text-muted-foreground" htmlFor={`clinical-${section.key}`}>
                    Новая запись
                  </label>
                  <input
                    id={`clinical-${section.key}`}
                    autoFocus
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    placeholder={section.placeholder}
                    autoComplete="off"
                    className="min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-base sm:text-sm"
                  />
                  <div className="grid grid-cols-2 gap-2 sm:flex">
                    <button
                      type="submit"
                      disabled={!value.trim() || addMutation.isPending}
                      className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                    >
                      {addMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                      Сохранить
                    </button>
                    <button
                      type="button"
                      disabled={addMutation.isPending}
                      onClick={() => {
                        setEditingSection(null);
                        setValue("");
                      }}
                      className="min-h-11 rounded-xl border border-border px-4 py-2 text-sm text-muted-foreground disabled:opacity-50"
                    >
                      Отмена
                    </button>
                  </div>
                </form>
              )}

              {!isEditing && (
                <div className="mt-4 grid gap-2 sm:flex sm:flex-wrap">
                  <button
                    type="button"
                    disabled={!consentActive || isBusy}
                    onClick={() => {
                      setEditingSection(section.key);
                      setValue("");
                    }}
                    className="inline-flex min-h-11 w-full items-center justify-center gap-1.5 rounded-xl border border-border px-3 py-2 text-sm font-medium sm:w-auto disabled:opacity-50"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" /> Добавить запись
                  </button>
                  {records.length === 0 && !state.confirmed_empty && (
                    <button
                      type="button"
                      disabled={!consentActive || isBusy}
                      onClick={() => reviewMutation.mutate({ section: section.key, confirmedEmpty: true })}
                      className="min-h-11 w-full rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-primary sm:w-auto disabled:opacity-50"
                    >
                      {clinicalEmptyActionLabel(section.emptyLabel)}
                    </button>
                  )}
                  {state.confirmed_empty && (
                    <button
                      type="button"
                      disabled={!consentActive || isBusy}
                      onClick={() => reviewMutation.mutate({ section: section.key, confirmedEmpty: false })}
                      className="min-h-11 w-full rounded-xl px-3 py-2 text-sm text-muted-foreground sm:w-auto disabled:opacity-50"
                    >
                      Снять подтверждение
                    </button>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {!consentActive && (
        <div className="mt-4 rounded-xl border border-border bg-muted/30 px-3 py-3 text-sm text-muted-foreground">
          Чтобы добавлять медицинские сведения, сначала примите согласие на обработку данных здоровья выше на странице.
        </div>
      )}
      {(addMutation.error || reviewMutation.error) && (
        <p className="mt-3 text-sm text-destructive" role="alert">
          {(addMutation.error ?? reviewMutation.error)?.message}
        </p>
      )}
      {(addMutation.isPending || reviewMutation.isPending) && (
        <span className="sr-only" aria-live="polite">
          Сохраняем изменения
        </span>
      )}
    </section>
  );
}
