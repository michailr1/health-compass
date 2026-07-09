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
  { key: "conditions", title: "Состояния", emptyLabel: "Состояний нет", placeholder: "Название состояния" },
  { key: "allergies", title: "Аллергии и непереносимости", emptyLabel: "Аллергий нет", placeholder: "Вещество или продукт" },
  { key: "medications", title: "Лекарства", emptyLabel: "Постоянных лекарств нет", placeholder: "Название лекарства" },
  { key: "supplements", title: "Добавки", emptyLabel: "Добавок нет", placeholder: "Название добавки" },
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
      <section className="hm-card grid min-h-40 place-items-center p-5">
        <Loader2 className="h-5 w-5 animate-spin" />
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="hm-card p-5 text-sm text-destructive">
        Не удалось загрузить клинический контекст.
      </section>
    );
  }

  return (
    <section className="hm-card p-5 md:p-6">
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 h-5 w-5 text-primary" />
        <div>
          <h2 className="font-display text-lg font-semibold">Клинический контекст</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Эти сведения помогают безопасно интерпретировать данные. Их можно заполнить позже.
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {SECTIONS.map((section) => {
          const state = data.summary.sections[section.key];
          const records = data[section.key];
          const isEditing = editingSection === section.key;
          return (
            <article key={section.key} className="rounded-2xl border border-border/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-medium">{section.title}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {clinicalSectionStatusLabel(state)}
                  </p>
                </div>
                {state.confirmed_empty && <CheckCircle2 className="h-5 w-5 text-success" />}
              </div>

              {records.length > 0 && (
                <div className="mt-3 space-y-2">
                  {records.slice(0, 3).map((record) => (
                    <div key={record.id} className="rounded-xl bg-muted/40 px-3 py-2 text-sm">
                      {clinicalRecordLabel(record)}
                    </div>
                  ))}
                  {records.length > 3 && (
                    <p className="text-xs text-muted-foreground">Ещё записей: {records.length - 3}</p>
                  )}
                </div>
              )}

              {isEditing && (
                <div className="mt-3 space-y-2">
                  <input
                    autoFocus
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    placeholder={section.placeholder}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={!value.trim() || addMutation.isPending}
                      onClick={() => addMutation.mutate({ section: section.key, name: value.trim() })}
                      className="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
                    >
                      Сохранить
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingSection(null);
                        setValue("");
                      }}
                      className="px-3 py-2 text-sm text-muted-foreground"
                    >
                      Отмена
                    </button>
                  </div>
                </div>
              )}

              {!isEditing && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={!consentActive}
                    onClick={() => {
                      setEditingSection(section.key);
                      setValue("");
                    }}
                    className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-50"
                  >
                    <Plus className="h-4 w-4" /> Добавить
                  </button>
                  {records.length === 0 && !state.confirmed_empty && (
                    <button
                      type="button"
                      disabled={!consentActive || reviewMutation.isPending}
                      onClick={() => reviewMutation.mutate({ section: section.key, confirmedEmpty: true })}
                      className="rounded-lg px-3 py-2 text-sm text-primary disabled:opacity-50"
                    >
                      {section.emptyLabel}
                    </button>
                  )}
                  {state.confirmed_empty && (
                    <button
                      type="button"
                      disabled={!consentActive || reviewMutation.isPending}
                      onClick={() => reviewMutation.mutate({ section: section.key, confirmedEmpty: false })}
                      className="rounded-lg px-3 py-2 text-sm text-muted-foreground disabled:opacity-50"
                    >
                      Изменить статус
                    </button>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>

      {!consentActive && (
        <p className="mt-4 text-xs text-muted-foreground">
          Для добавления медицинских сведений сначала примите согласие на обработку данных здоровья.
        </p>
      )}
      {(addMutation.error || reviewMutation.error) && (
        <p className="mt-3 text-sm text-destructive">
          {(addMutation.error ?? reviewMutation.error)?.message}
        </p>
      )}
    </section>
  );
}
