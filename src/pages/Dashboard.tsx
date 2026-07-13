import { useQuery } from "@tanstack/react-query";
import { Activity, Bed, CalendarClock, Dna, Gauge, AlertTriangle, ArrowRight, Info, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

import { DashboardProfileContextCard } from "@/components/DashboardProfileContextCard";
import {
  ApiError,
  apiGet,
  type DashboardSnapshot,
  type HealthProfile,
  type ProfileCompletionSummary,
} from "@/lib/api";
import { getDocumentIntakeCapabilities } from "@/lib/documentApi";
import { getEmptyDashboardPrimaryAction } from "@/lib/productUx";

const fmt = new Intl.NumberFormat("ru-RU");

function Stat({
  icon: Icon, label, value, hint,
}: { icon: React.ComponentType<{ className?: string }>; label: string; value: string; hint?: string }) {
  return (
    <div className="hm-card p-5 animate-fade-in">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3.5 w-3.5 text-primary" />
        {label}
      </div>
      <div className="mt-2 font-display text-2xl font-semibold tracking-tight md:text-3xl">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const priorityStyles: Record<string, string> = {
  high: "border-destructive/40 bg-destructive/10 text-destructive",
  medium: "border-warning/40 bg-warning/10 text-warning",
  info: "border-primary/40 bg-primary/10 text-primary",
};
const priorityLabel: Record<string, string> = { high: "Высокий", medium: "Средний", info: "Инфо" };
const priorityIcon: Record<string, React.ComponentType<{ className?: string }>> = {
  high: AlertTriangle, medium: AlertTriangle, info: Info,
};

export async function loadDashboard() {
  const profiles = await apiGet<HealthProfile[]>("/profiles");
  const profile = profiles[0];
  if (!profile) return { profile: null, dashboard: null, completion: null, uploadEnabled: false };

  const completionPromise = apiGet<ProfileCompletionSummary>(`/profiles/${profile.id}/completion`)
    .catch(() => null);
  const uploadEnabledPromise = getDocumentIntakeCapabilities(profile.id)
    .then((capabilities) => capabilities.upload_enabled)
    .catch(() => false);

  try {
    const dashboard = await apiGet<DashboardSnapshot>(`/profiles/${profile.id}/dashboard`);
    return {
      profile,
      dashboard,
      completion: await completionPromise,
      uploadEnabled: await uploadEnabledPromise,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return {
        profile,
        dashboard: null,
        completion: await completionPromise,
        uploadEnabled: await uploadEnabledPromise,
      };
    }
    throw error;
  }
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: loadDashboard });

  if (isLoading) {
    return (
      <div className="hm-card grid min-h-64 place-items-center p-8 text-sm text-muted-foreground">
        <div className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Загружаю данные…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="hm-card border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
        Не удалось загрузить главную: {error instanceof Error ? error.message : "неизвестная ошибка"}
      </div>
    );
  }

  if (!data?.profile) {
    return (
      <div className="hm-card p-6 md:p-8">
        <h1 className="font-display text-2xl font-semibold tracking-tight">Главная</h1>
        <p className="mt-2 text-sm text-muted-foreground">Профиль здоровья пока не создан.</p>
        <Link
          to="/app/profile"
          className="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-gradient-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-elegant hover:opacity-90"
        >
          Создать профиль здоровья <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    );
  }

  if (!data.dashboard) {
    const primaryAction = getEmptyDashboardPrimaryAction(data.uploadEnabled);
    return (
      <div className="space-y-6">
        <header>
          <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Главная</h1>
          <p className="mt-1 text-sm text-muted-foreground">Профиль: {data.profile.display_name}</p>
        </header>
        {data.completion && <DashboardProfileContextCard completion={data.completion} />}
        <div className="hm-card p-6 md:p-8">
          <h2 className="font-display text-xl font-semibold">Пока нет данных для сводки</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            {primaryAction.description} Анкету можно заполнять постепенно.
          </p>
          <Link
            to={primaryAction.to}
            className="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-gradient-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-elegant hover:opacity-90"
          >
            {primaryAction.label} <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    );
  }

  const s = data.dashboard.summary;
  const priorities = data.dashboard.priorities;
  const fullProfileContext = data.completion?.progress_percent === 100;

  return (
    <div className="space-y-6">
      <header className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Главная</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Профиль: {data.profile.display_name}. Показатели и контекст профиля учитываются отдельно.
          </p>
        </div>
        <div className="hm-chip"><span className="h-1.5 w-1.5 rounded-full bg-success" /> Данные актуальны</div>
      </header>

      {data.completion && <DashboardProfileContextCard completion={data.completion} />}

      <div className="hm-card relative overflow-hidden p-6 md:p-8">
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative grid gap-6 md:grid-cols-[auto,1fr] md:items-center">
          <div className="flex items-center gap-5">
            <div className="grid h-24 w-24 place-items-center rounded-full border border-primary/40 bg-primary/10 shadow-elegant">
              <div className="text-center">
                <div className="font-display text-3xl font-semibold text-primary">{s.observationIndex}</div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">/ 100</div>
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Интегральный индекс наблюдения</div>
              <div className="mt-1 font-display text-xl font-semibold">Наблюдение стабильно</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {fullProfileContext
                  ? "Физиологические данные дополнены просмотренным контекстом профиля."
                  : "Физиологические данные доступны; контекст профиля можно дополнить для более точной персонализации."}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MiniKpi label="HRV" value="+23%" tone="positive" />
            <MiniKpi label="Readiness" value="+15%" tone="positive" />
            <MiniKpi label="Ночной пульс" value="−5%" tone="positive" />
            <MiniKpi label="Шаги" value="−39%" tone="negative" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat icon={Bed} label="Средний сон" value={`${s.avgSleep.hours} ч ${s.avgSleep.minutes} мин`} hint="из snapshot профиля" />
        <Stat icon={Gauge} label="Ночей < 7 часов" value={`${s.shortNightsPct}%`} hint="цель — стабильные 7 ч 30 мин" />
        <Stat icon={CalendarClock} label="Дней активности" value={fmt.format(s.activeDays)} hint="с носимым устройством" />
        <Stat icon={Dna} label="Генетических позиций" value={fmt.format(s.geneticPositions)} hint="после QC" />
      </div>

      <section className="hm-card p-5 md:p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold tracking-tight">Ключевые приоритеты</h2>
          <Link to="/app/plan" className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
            План действий <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        <ul className="grid gap-3 md:grid-cols-2">
          {priorities.map((p) => {
            const Icon = priorityIcon[p.priority];
            return (
              <li key={p.id} className="rounded-xl border border-border/60 bg-surface-2/60 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg border ${priorityStyles[p.priority]}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="font-medium">{p.title}</div>
                      <div className="mt-1 text-sm text-muted-foreground">{p.description}</div>
                    </div>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${priorityStyles[p.priority]}`}>
                    {priorityLabel[p.priority]}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="hm-card flex flex-col items-start justify-between gap-3 p-5 md:flex-row md:items-center">
        <div className="flex items-center gap-3">
          <Activity className="h-5 w-5 text-primary" />
          <div>
            <div className="font-medium">Сравнить окна физиологии</div>
            <div className="text-sm text-muted-foreground">Первые и последние 30 дней, индексированы к 100.</div>
          </div>
        </div>
        <Link
          to="/app/sleep"
          className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-elegant hover:opacity-90"
        >
          Открыть сон <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}

function MiniKpi({ label, value, tone }: { label: string; value: string; tone: "positive" | "negative" }) {
  return (
    <div className="rounded-xl border border-border/60 bg-surface-2/60 p-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`mt-1 font-display text-lg font-semibold ${tone === "positive" ? "text-success" : "text-warning"}`}>
        {value}
      </div>
    </div>
  );
}
