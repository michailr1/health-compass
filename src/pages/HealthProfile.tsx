import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Scale, ShieldCheck, UserRound } from "lucide-react";

import { ClinicalContextSection } from "@/components/ClinicalContextSection";
import {
  apiGet,
  apiPatch,
  apiPost,
  type BodyMeasurement,
  type ConsentStatus,
  type HealthProfile,
} from "@/lib/api";

const CONSENT_VERSION = "health-data-processing-v1";
const WEIGHT_WARNING_MIN_KG = 20;
const WEIGHT_WARNING_MAX_KG = 400;
const COMMON_TIMEZONES = [
  "Europe/Moscow",
  "Europe/Paris",
  "Europe/London",
  "Asia/Dubai",
  "Asia/Bangkok",
  "Asia/Shanghai",
  "America/New_York",
  "America/Los_Angeles",
  "UTC",
];

function detectBrowserTimezone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

async function loadProfilePage() {
  const profiles = await apiGet<HealthProfile[]>("/profiles");
  const first = profiles[0];
  if (!first) return { profile: null, measurements: [], consent: null };
  const [profile, measurements, consent] = await Promise.all([
    apiGet<HealthProfile>(`/profiles/${first.id}`),
    apiGet<BodyMeasurement[]>(`/profiles/${first.id}/body-measurements`),
    apiGet<ConsentStatus>("/consents/health-data-processing"),
  ]);
  return { profile, measurements, consent };
}

export default function HealthProfilePage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["health-profile"],
    queryFn: loadProfilePage,
  });
  const profile = data?.profile ?? null;
  const consentActive = Boolean(data?.consent?.active);
  const detectedTimezone = useMemo(detectBrowserTimezone, []);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [weight, setWeight] = useState("");
  const [timezoneEditing, setTimezoneEditing] = useState(false);
  const [timezoneValue, setTimezoneValue] = useState("");

  useEffect(() => {
    if (!profile) return;
    setDraft({
      display_name: profile.display_name,
      date_of_birth: profile.date_of_birth ?? "",
      sex: profile.sex ?? "",
      height_cm: profile.height_cm ?? "",
    });
    setTimezoneValue(profile.timezone ?? detectedTimezone ?? "");
  }, [detectedTimezone, profile?.id]);

  const patchMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiPatch<HealthProfile>(`/profiles/${profile!.id}`, payload),
    onMutate: () => setSaveState("saving"),
    onSuccess: () => {
      setSaveState("saved");
      queryClient.invalidateQueries({ queryKey: ["health-profile"] });
    },
    onError: () => setSaveState("error"),
  });

  useEffect(() => {
    if (!profile || Object.keys(draft).length === 0) return;
    const timer = window.setTimeout(() => {
      const payload: Record<string, unknown> = {
        display_name: draft.display_name.trim(),
      };
      if (consentActive) {
        payload.date_of_birth = draft.date_of_birth || null;
        payload.sex = draft.sex || null;
        payload.height_cm = draft.height_cm || null;
        if (!profile.timezone && detectedTimezone) payload.timezone = detectedTimezone;
      }

      const timezoneUnchanged =
        !("timezone" in payload) || payload.timezone === profile.timezone;
      const medicalUnchanged =
        !consentActive ||
        (payload.date_of_birth === profile.date_of_birth &&
          payload.sex === profile.sex &&
          String(payload.height_cm ?? "") === String(profile.height_cm ?? "") &&
          timezoneUnchanged);
      const unchanged = payload.display_name === profile.display_name && medicalUnchanged;
      if (!unchanged && draft.display_name.trim()) patchMutation.mutate(payload);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [consentActive, detectedTimezone, draft, profile?.id, profile?.timezone]);

  const consentMutation = useMutation({
    mutationFn: () =>
      apiPost<ConsentStatus>("/consents/health-data-processing/accept", {
        document_version: CONSENT_VERSION,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["health-profile"] }),
  });

  const weightMutation = useMutation({
    mutationFn: (confirmUnusualValue: boolean) =>
      apiPost<BodyMeasurement>(`/profiles/${profile!.id}/body-measurements`, {
        measurement_type: "weight",
        value: Number(weight),
        unit: "kg",
        measured_at: new Date().toISOString(),
        confirm_unusual_value: confirmUnusualValue,
      }),
    onSuccess: () => {
      setWeight("");
      queryClient.invalidateQueries({ queryKey: ["health-profile"] });
    },
  });

  const addWeight = () => {
    const numericWeight = Number(weight);
    if (!Number.isFinite(numericWeight) || numericWeight <= 0) return;
    const unusual = numericWeight < WEIGHT_WARNING_MIN_KG || numericWeight > WEIGHT_WARNING_MAX_KG;
    if (unusual) {
      const confirmed = window.confirm(
        `Вес ${numericWeight.toLocaleString("ru-RU")} кг выглядит необычно. Проверьте значение и единицы. Сохранить?`,
      );
      if (!confirmed) return;
    }
    weightMutation.mutate(unusual);
  };

  const saveTimezone = () => {
    const value = timezoneValue.trim();
    if (!value || value === profile?.timezone) {
      setTimezoneEditing(false);
      return;
    }
    patchMutation.mutate({ timezone: value });
    setTimezoneEditing(false);
  };

  const useDetectedTimezone = () => {
    if (!detectedTimezone) return;
    setTimezoneValue(detectedTimezone);
    if (detectedTimezone !== profile?.timezone) {
      patchMutation.mutate({ timezone: detectedTimezone });
    }
    setTimezoneEditing(false);
  };

  const readinessItems = useMemo(() => {
    const readiness = profile?.readiness;
    if (!readiness) return [];
    return [
      ["Возрастные референсы", readiness.age_references],
      ["Референсы с учётом пола", readiness.sex_specific_references],
      ["Расчёт ИМТ", readiness.bmi],
      ["Локальное время событий", readiness.local_time_context],
    ] as Array<[string, boolean]>;
  }, [profile?.readiness]);

  if (isLoading) {
    return (
      <div className="hm-card grid min-h-64 place-items-center">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }
  if (error) {
    return <div className="hm-card p-6 text-destructive">Не удалось загрузить профиль.</div>;
  }
  if (!profile) {
    return <div className="hm-card p-6">Профиль пока не создан.</div>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold md:text-3xl">Профиль здоровья</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Базовые данные для референсов и динамики. Поля можно заполнить позже.
        </p>
      </header>

      {!consentActive && (
        <section className="hm-card border-primary/30 p-5">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 text-primary" />
            <div className="flex-1">
              <h2 className="font-medium">Согласие на обработку данных здоровья</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Нужно только перед сохранением медицинских полей и измерений.
              </p>
              <button
                type="button"
                onClick={() => consentMutation.mutate()}
                disabled={consentMutation.isPending}
                className="mt-3 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
              >
                Принять и продолжить
              </button>
            </div>
          </div>
        </section>
      )}

      <section className="hm-card p-5 md:p-6">
        <div className="mb-4 flex items-center gap-2">
          <UserRound className="h-5 w-5 text-primary" />
          <h2 className="font-display text-lg font-semibold">Основные сведения</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Имя профиля" value={draft.display_name ?? ""} onChange={(value) => setDraft((state) => ({ ...state, display_name: value }))} />
          <Field label="Дата рождения" type="date" value={draft.date_of_birth ?? ""} disabled={!consentActive} onChange={(value) => setDraft((state) => ({ ...state, date_of_birth: value }))} />
          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground">Пол</span>
            <select disabled={!consentActive} value={draft.sex ?? ""} onChange={(event) => setDraft((state) => ({ ...state, sex: event.target.value }))} className="w-full rounded-xl border border-border bg-background px-3 py-2.5">
              <option value="">Не выбрано</option>
              <option value="male">Мужской</option>
              <option value="female">Женский</option>
              <option value="not_specified">Предпочитаю не указывать</option>
            </select>
          </label>
          <Field label="Рост, см" type="number" value={draft.height_cm ?? ""} disabled={!consentActive} onChange={(value) => setDraft((state) => ({ ...state, height_cm: value }))} />
        </div>

        {consentActive && (
          <div className="mt-4 rounded-xl border border-border/60 p-3 text-sm">
            {!timezoneEditing ? (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="text-muted-foreground">Часовой пояс: </span>
                  <span>{profile.timezone ?? detectedTimezone ?? "не определён"}</span>
                  {!profile.timezone && detectedTimezone && (
                    <span className="ml-2 text-xs text-muted-foreground">определён автоматически</span>
                  )}
                </div>
                <button type="button" onClick={() => setTimezoneEditing(true)} className="text-primary hover:underline">
                  Изменить
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <label className="block text-muted-foreground" htmlFor="timezone-input">Часовой пояс</label>
                <input
                  id="timezone-input"
                  list="common-timezones"
                  value={timezoneValue}
                  onChange={(event) => setTimezoneValue(event.target.value)}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2.5"
                  placeholder="Europe/Moscow"
                />
                <datalist id="common-timezones">
                  {COMMON_TIMEZONES.map((timezone) => <option key={timezone} value={timezone} />)}
                </datalist>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={saveTimezone} className="rounded-lg bg-primary px-3 py-2 text-primary-foreground">Сохранить</button>
                  {detectedTimezone && (
                    <button type="button" onClick={useDetectedTimezone} className="rounded-lg border border-border px-3 py-2">Использовать текущий</button>
                  )}
                  <button type="button" onClick={() => setTimezoneEditing(false)} className="px-3 py-2 text-muted-foreground">Отмена</button>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-3 text-xs text-muted-foreground">
          {saveState === "saving" && "Сохраняется…"}
          {saveState === "saved" && "Сохранено"}
          {saveState === "error" && "Не удалось сохранить"}
        </div>
      </section>

      <ClinicalContextSection profileId={profile.id} consentActive={consentActive} />

      <section className="hm-card p-5 md:p-6">
        <h2 className="font-display text-lg font-semibold">Готовность контекста</h2>
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          {readinessItems.map(([label, ready]) => (
            <div key={label} className="flex items-center gap-2 rounded-xl border border-border/60 p-3 text-sm">
              <CheckCircle2 className={`h-4 w-4 ${ready ? "text-success" : "text-muted-foreground"}`} />
              <span>{ready ? `Готово: ${label}` : `Можно дополнить: ${label}`}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="hm-card p-5 md:p-6">
        <div className="mb-4 flex items-center gap-2">
          <Scale className="h-5 w-5 text-primary" />
          <h2 className="font-display text-lg font-semibold">Вес</h2>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input disabled={!consentActive} type="number" step="0.1" min="0" value={weight} onChange={(event) => setWeight(event.target.value)} placeholder="Вес, кг" className="rounded-xl border border-border bg-background px-3 py-2.5" />
          <button disabled={!consentActive || !weight || weightMutation.isPending} onClick={addWeight} className="rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50">
            Добавить измерение
          </button>
        </div>
        {weightMutation.error && <p className="mt-2 text-sm text-destructive">{weightMutation.error.message}</p>}
        <div className="mt-4 space-y-2">
          {(data?.measurements ?? []).map((item) => (
            <div key={item.id} className="flex items-center justify-between rounded-xl border border-border/60 p-3 text-sm">
              <span>{Number(item.value).toLocaleString("ru-RU")} кг</span>
              <span className="text-muted-foreground">{new Date(item.measured_at).toLocaleString("ru-RU")}</span>
            </div>
          ))}
          {(data?.measurements ?? []).length === 0 && <p className="text-sm text-muted-foreground">Измерений пока нет.</p>}
        </div>
      </section>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", disabled = false }: { label: string; value: string; onChange: (value: string) => void; type?: string; disabled?: boolean }) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <input disabled={disabled} type={type} value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-xl border border-border bg-background px-3 py-2.5 disabled:opacity-60" />
    </label>
  );
}
