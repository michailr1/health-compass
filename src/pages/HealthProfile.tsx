import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Scale, ShieldCheck, UserRound } from "lucide-react";

import {
  apiGet,
  apiPatch,
  apiPost,
  type BodyMeasurement,
  type ConsentStatus,
  type HealthProfile,
} from "@/lib/api";

const CONSENT_VERSION = "health-data-processing-v1";

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
  const [draft, setDraft] = useState<Record<string, string>>( {} );
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [weight, setWeight] = useState("");

  useEffect(() => {
    if (!profile) return;
    setDraft({
      display_name: profile.display_name,
      date_of_birth: profile.date_of_birth ?? "",
      sex: profile.sex ?? "not_specified",
      height_cm: profile.height_cm ?? "",
      timezone: profile.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
    });
  }, [profile?.id]);

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
      const payload = {
        display_name: draft.display_name,
        date_of_birth: draft.date_of_birth || null,
        sex: draft.sex || null,
        height_cm: draft.height_cm || null,
        timezone: draft.timezone || null,
      };
      const unchanged =
        payload.display_name === profile.display_name &&
        payload.date_of_birth === profile.date_of_birth &&
        payload.sex === (profile.sex ?? "not_specified") &&
        String(payload.height_cm ?? "") === String(profile.height_cm ?? "") &&
        payload.timezone === profile.timezone;
      if (!unchanged) patchMutation.mutate(payload);
    }, 800);
    return () => window.clearTimeout(timer);
  }, [draft, profile?.id]);

  const consentMutation = useMutation({
    mutationFn: () =>
      apiPost<ConsentStatus>("/consents/health-data-processing/accept", {
        document_version: CONSENT_VERSION,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["health-profile"] }),
  });

  const weightMutation = useMutation({
    mutationFn: () =>
      apiPost<BodyMeasurement>(`/profiles/${profile!.id}/body-measurements`, {
        measurement_type: "weight",
        value: Number(weight),
        unit: "kg",
        measured_at: new Date().toISOString(),
        confirm_unusual_value: false,
      }),
    onSuccess: () => {
      setWeight("");
      queryClient.invalidateQueries({ queryKey: ["health-profile"] });
    },
  });

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
    return <div className="hm-card grid min-h-64 place-items-center"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  }
  if (error) {
    return <div className="hm-card p-6 text-destructive">Не удалось загрузить профиль.</div>;
  }
  if (!profile) {
    return <div className="hm-card p-6">Профиль пока не создан.</div>;
  }

  const consentActive = Boolean(data?.consent?.active);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold md:text-3xl">Профиль здоровья</h1>
        <p className="mt-1 text-sm text-muted-foreground">Базовые данные для референсов и динамики. Поля можно заполнить позже.</p>
      </header>

      {!consentActive && (
        <section className="hm-card border-primary/30 p-5">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 text-primary" />
            <div className="flex-1">
              <h2 className="font-medium">Согласие на обработку данных здоровья</h2>
              <p className="mt-1 text-sm text-muted-foreground">Нужно только перед сохранением медицинских полей и измерений.</p>
              <button
                type="button"
                onClick={() => consentMutation.mutate()}
                className="mt-3 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                Принять и продолжить
              </button>
            </div>
          </div>
        </section>
      )}

      <section className="hm-card p-5 md:p-6">
        <div className="mb-4 flex items-center gap-2"><UserRound className="h-5 w-5 text-primary" /><h2 className="font-display text-lg font-semibold">Основные сведения</h2></div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Имя профиля" value={draft.display_name ?? ""} onChange={(value) => setDraft((s) => ({ ...s, display_name: value }))} />
          <Field label="Дата рождения" type="date" value={draft.date_of_birth ?? ""} disabled={!consentActive} onChange={(value) => setDraft((s) => ({ ...s, date_of_birth: value }))} />
          <label className="space-y-1.5 text-sm"><span className="text-muted-foreground">Пол</span><select disabled={!consentActive} value={draft.sex ?? "not_specified"} onChange={(e) => setDraft((s) => ({ ...s, sex: e.target.value }))} className="w-full rounded-xl border border-border bg-background px-3 py-2.5"><option value="male">Мужской</option><option value="female">Женский</option><option value="not_specified">Не указано</option></select></label>
          <Field label="Рост, см" type="number" value={draft.height_cm ?? ""} disabled={!consentActive} onChange={(value) => setDraft((s) => ({ ...s, height_cm: value }))} />
          <Field label="Часовой пояс" value={draft.timezone ?? ""} disabled={!consentActive} onChange={(value) => setDraft((s) => ({ ...s, timezone: value }))} />
        </div>
        <div className="mt-3 text-xs text-muted-foreground">
          {saveState === "saving" && "Сохраняется…"}
          {saveState === "saved" && "Сохранено"}
          {saveState === "error" && "Не удалось сохранить"}
        </div>
      </section>

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
        <div className="mb-4 flex items-center gap-2"><Scale className="h-5 w-5 text-primary" /><h2 className="font-display text-lg font-semibold">Вес</h2></div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input disabled={!consentActive} type="number" step="0.1" min="0" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="Вес, кг" className="rounded-xl border border-border bg-background px-3 py-2.5" />
          <button disabled={!consentActive || !weight || weightMutation.isPending} onClick={() => weightMutation.mutate()} className="rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50">Добавить измерение</button>
        </div>
        <div className="mt-4 space-y-2">
          {(data?.measurements ?? []).map((item) => (
            <div key={item.id} className="flex items-center justify-between rounded-xl border border-border/60 p-3 text-sm"><span>{Number(item.value).toLocaleString("ru-RU")} кг</span><span className="text-muted-foreground">{new Date(item.measured_at).toLocaleString("ru-RU")}</span></div>
          ))}
          {(data?.measurements ?? []).length === 0 && <p className="text-sm text-muted-foreground">Измерений пока нет.</p>}
        </div>
      </section>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", disabled = false }: { label: string; value: string; onChange: (value: string) => void; type?: string; disabled?: boolean }) {
  return <label className="space-y-1.5 text-sm"><span className="text-muted-foreground">{label}</span><input disabled={disabled} type={type} value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-xl border border-border bg-background px-3 py-2.5 disabled:opacity-60" /></label>;
}
