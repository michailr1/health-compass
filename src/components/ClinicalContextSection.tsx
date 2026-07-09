import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, Pill, Plus } from "lucide-react";

import {
  apiGet,
  apiPatch,
  apiPost,
  type ClinicalContextSummary,
  type ProfileAllergy,
  type ProfileMedication,
} from "@/lib/api";

type Props = {
  profileId: string;
  consentActive: boolean;
};

type AllergyDraft = {
  allergen: string;
  reaction: string;
  severity: ProfileAllergy["severity"];
};

type MedicationDraft = {
  medication_name: string;
  dose_text: string;
  schedule_text: string;
};

const emptyAllergy: AllergyDraft = { allergen: "", reaction: "", severity: "unknown" };
const emptyMedication: MedicationDraft = { medication_name: "", dose_text: "", schedule_text: "" };

export default function ClinicalContextSection({ profileId, consentActive }: Props) {
  const queryClient = useQueryClient();
  const [showAllergyForm, setShowAllergyForm] = useState(false);
  const [showMedicationForm, setShowMedicationForm] = useState(false);
  const [allergyDraft, setAllergyDraft] = useState<AllergyDraft>(emptyAllergy);
  const [medicationDraft, setMedicationDraft] = useState<MedicationDraft>(emptyMedication);

  const summaryQuery = useQuery({
    queryKey: ["clinical-context", profileId],
    queryFn: () => apiGet<ClinicalContextSummary>(`/profiles/${profileId}/clinical-context`),
  });
  const allergiesQuery = useQuery({
    queryKey: ["profile-allergies", profileId],
    queryFn: () => apiGet<ProfileAllergy[]>(`/profiles/${profileId}/allergies`),
  });
  const medicationsQuery = useQuery({
    queryKey: ["profile-medications", profileId],
    queryFn: () => apiGet<ProfileMedication[]>(`/profiles/${profileId}/medications`),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["clinical-context", profileId] }),
      queryClient.invalidateQueries({ queryKey: ["profile-allergies", profileId] }),
      queryClient.invalidateQueries({ queryKey: ["profile-medications", profileId] }),
      queryClient.invalidateQueries({ queryKey: ["health-profile"] }),
    ]);
  };

  const addAllergy = useMutation({
    mutationFn: () =>
      apiPost<ProfileAllergy>(`/profiles/${profileId}/allergies`, {
        allergen: allergyDraft.allergen,
        reaction: allergyDraft.reaction || null,
        severity: allergyDraft.severity,
      }),
    onSuccess: async () => {
      setAllergyDraft(emptyAllergy);
      setShowAllergyForm(false);
      await refresh();
    },
  });

  const addMedication = useMutation({
    mutationFn: () =>
      apiPost<ProfileMedication>(`/profiles/${profileId}/medications`, {
        medication_name: medicationDraft.medication_name,
        dose_text: medicationDraft.dose_text || null,
        schedule_text: medicationDraft.schedule_text || null,
      }),
    onSuccess: async () => {
      setMedicationDraft(emptyMedication);
      setShowMedicationForm(false);
      await refresh();
    },
  });

  const reviewSection = useMutation({
    mutationFn: (section: "allergies" | "medications") =>
      apiPost<ClinicalContextSummary>(`/profiles/${profileId}/clinical-context/review`, { section }),
    onSuccess: refresh,
  });

  const updateAllergy = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProfileAllergy["status"] }) =>
      apiPatch<ProfileAllergy>(`/profiles/${profileId}/allergies/${id}`, { status }),
    onSuccess: refresh,
  });

  const updateMedication = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProfileMedication["status"] }) =>
      apiPatch<ProfileMedication>(`/profiles/${profileId}/medications/${id}`, { status }),
    onSuccess: refresh,
  });

  const isLoading = summaryQuery.isLoading || allergiesQuery.isLoading || medicationsQuery.isLoading;
  const hasError = summaryQuery.error || allergiesQuery.error || medicationsQuery.error;
  const summary = summaryQuery.data;
  const allergies = allergiesQuery.data ?? [];
  const medications = medicationsQuery.data ?? [];

  return (
    <section className="space-y-4">
      <div>
        <h2 className="font-display text-xl font-semibold">Клинический контекст</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Сведения введены пользователем и не заменяют назначения врача.
        </p>
      </div>

      {!consentActive && (
        <div className="rounded-xl border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
          Примите согласие на обработку данных здоровья, чтобы добавлять аллергии и лекарства.
        </div>
      )}

      {isLoading && (
        <div className="hm-card flex items-center gap-2 p-5 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Загружаю клинический контекст…
        </div>
      )}

      {hasError && (
        <div className="hm-card border-destructive/30 p-5 text-sm text-destructive">
          Не удалось загрузить клинический контекст.
        </div>
      )}

      {!isLoading && !hasError && (
        <div className="grid gap-4 lg:grid-cols-2">
          <article className="hm-card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-warning" />
                  <h3 className="font-display text-lg font-semibold">Аллергии</h3>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {summary?.allergies_reviewed_at
                    ? `Проверено ${new Date(summary.allergies_reviewed_at).toLocaleDateString("ru-RU")}`
                    : "Раздел ещё не проверен"}
                </p>
              </div>
              <button
                type="button"
                disabled={!consentActive}
                onClick={() => setShowAllergyForm((value) => !value)}
                className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-muted/40 disabled:opacity-50"
              >
                <Plus className="h-3.5 w-3.5" /> Добавить
              </button>
            </div>

            {showAllergyForm && (
              <div className="mt-4 space-y-3 rounded-xl border border-border bg-muted/20 p-3">
                <input
                  value={allergyDraft.allergen}
                  onChange={(event) => setAllergyDraft((state) => ({ ...state, allergen: event.target.value }))}
                  placeholder="Аллерген или вещество"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                />
                <input
                  value={allergyDraft.reaction}
                  onChange={(event) => setAllergyDraft((state) => ({ ...state, reaction: event.target.value }))}
                  placeholder="Реакция, если известна"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                />
                <select
                  value={allergyDraft.severity}
                  onChange={(event) =>
                    setAllergyDraft((state) => ({
                      ...state,
                      severity: event.target.value as ProfileAllergy["severity"],
                    }))
                  }
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="unknown">Тяжесть неизвестна</option>
                  <option value="mild">Лёгкая</option>
                  <option value="moderate">Средняя</option>
                  <option value="severe">Тяжёлая</option>
                </select>
                <button
                  type="button"
                  disabled={!allergyDraft.allergen.trim() || addAllergy.isPending}
                  onClick={() => addAllergy.mutate()}
                  className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                >
                  Сохранить аллергию
                </button>
              </div>
            )}

            <div className="mt-4 space-y-2">
              {allergies.filter((item) => item.status !== "entered_in_error").map((item) => (
                <div
                  key={item.id}
                  className={`rounded-xl border p-3 text-sm ${
                    item.status === "active" && item.severity === "severe"
                      ? "border-destructive/40 bg-destructive/10"
                      : "border-border/60"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{item.allergen}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {item.reaction || "Реакция не указана"} · {severityLabel(item.severity)}
                      </div>
                    </div>
                    {item.status === "active" ? (
                      <button
                        type="button"
                        onClick={() => updateAllergy.mutate({ id: item.id, status: "resolved" })}
                        className="text-xs text-primary hover:underline"
                      >
                        Больше не актуально
                      </button>
                    ) : (
                      <span className="text-xs text-muted-foreground">Неактивна</span>
                    )}
                  </div>
                </div>
              ))}
              {allergies.length === 0 && (
                <p className="text-sm text-muted-foreground">Записей об аллергиях пока нет.</p>
              )}
            </div>

            {allergies.filter((item) => item.status === "active").length === 0 && (
              <button
                type="button"
                disabled={!consentActive || reviewSection.isPending}
                onClick={() => reviewSection.mutate("allergies")}
                className="mt-4 inline-flex items-center gap-1.5 text-xs text-primary hover:underline disabled:opacity-50"
              >
                <CheckCircle2 className="h-3.5 w-3.5" /> Подтвердить, что известных аллергий нет
              </button>
            )}
          </article>

          <article className="hm-card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Pill className="h-5 w-5 text-primary" />
                  <h3 className="font-display text-lg font-semibold">Текущие лекарства</h3>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {summary?.medications_reviewed_at
                    ? `Проверено ${new Date(summary.medications_reviewed_at).toLocaleDateString("ru-RU")}`
                    : "Раздел ещё не проверен"}
                </p>
              </div>
              <button
                type="button"
                disabled={!consentActive}
                onClick={() => setShowMedicationForm((value) => !value)}
                className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-muted/40 disabled:opacity-50"
              >
                <Plus className="h-3.5 w-3.5" /> Добавить
              </button>
            </div>

            {showMedicationForm && (
              <div className="mt-4 space-y-3 rounded-xl border border-border bg-muted/20 p-3">
                <input
                  value={medicationDraft.medication_name}
                  onChange={(event) =>
                    setMedicationDraft((state) => ({ ...state, medication_name: event.target.value }))
                  }
                  placeholder="Название препарата"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                />
                <input
                  value={medicationDraft.dose_text}
                  onChange={(event) => setMedicationDraft((state) => ({ ...state, dose_text: event.target.value }))}
                  placeholder="Доза, например 500 мг"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                />
                <input
                  value={medicationDraft.schedule_text}
                  onChange={(event) =>
                    setMedicationDraft((state) => ({ ...state, schedule_text: event.target.value }))
                  }
                  placeholder="Как принимаете, например утром"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  disabled={!medicationDraft.medication_name.trim() || addMedication.isPending}
                  onClick={() => addMedication.mutate()}
                  className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
                >
                  Сохранить лекарство
                </button>
              </div>
            )}

            <div className="mt-4 space-y-2">
              {medications.filter((item) => item.status !== "entered_in_error").map((item) => (
                <div key={item.id} className="rounded-xl border border-border/60 p-3 text-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{item.medication_name}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {[item.dose_text, item.schedule_text].filter(Boolean).join(" · ") || "Схема не указана"}
                      </div>
                    </div>
                    {item.status === "active" || item.status === "paused" ? (
                      <button
                        type="button"
                        onClick={() => updateMedication.mutate({ id: item.id, status: "stopped" })}
                        className="text-xs text-primary hover:underline"
                      >
                        Завершить
                      </button>
                    ) : (
                      <span className="text-xs text-muted-foreground">Завершено</span>
                    )}
                  </div>
                </div>
              ))}
              {medications.length === 0 && (
                <p className="text-sm text-muted-foreground">Постоянные лекарства пока не указаны.</p>
              )}
            </div>

            {medications.filter((item) => item.status === "active").length === 0 && (
              <button
                type="button"
                disabled={!consentActive || reviewSection.isPending}
                onClick={() => reviewSection.mutate("medications")}
                className="mt-4 inline-flex items-center gap-1.5 text-xs text-primary hover:underline disabled:opacity-50"
              >
                <CheckCircle2 className="h-3.5 w-3.5" /> Подтвердить, что постоянных лекарств нет
              </button>
            )}
          </article>
        </div>
      )}
    </section>
  );
}

export function severityLabel(value: ProfileAllergy["severity"]): string {
  return {
    unknown: "тяжесть неизвестна",
    mild: "лёгкая",
    moderate: "средняя",
    severe: "тяжёлая",
  }[value];
}
