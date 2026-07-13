import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bed,
  CalendarClock,
  Dna,
  Gauge,
  Info,
  Loader2,
} from "lucide-react";
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
import { getEmptyDashboardPrimaryAction, isDemoDataSource } from "@/lib/productUx";

const fmt = new Intl.NumberFormat("ru-RU");

function Stat({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="hm-card p-5 animate-fade-in">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3.5 w-3.5 text-primary" />
        {label}
      </div>
      <div className="mt-2 font-display text-2xl font-semibold tracking-tight md:text-3xl">
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const priorityStyles: Record<string, string> = {
  high: "border-destructive/40 bg-destructive/10 text-destructive",
  medium: "border-warning/40 bg-warning/10 text-warning",
  info: "border-primary/40 bg-primary/10 text-primary",
};
const priorityLabel: Record<string, string> = {
  high: "Высокий",
  medium: "Средний",
  info: "Инфо",
};
const priorityIcon: Record<string, React.ComponentType<{ className?: string }>> = {
  high: AlertTriangle,
  medium: AlertTriangle,
  info: Info,
};

export async function loadDashboard() {
  const profiles = await apiGet<HealthProfile[]>("/profiles");
  const profile = profiles[0];
  if (!profile) {
    return { profile: null, dashboard: null, completion: null, uploadEnabled: false };
  }

  const completionPromise = apiGet<ProfileCompletionSummary>(
    `/profiles/${profile.id}/completion`,
  ).catch(() => null);
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
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: loadDashboard,
  });

  if (isLoading) {
    return (
      <div className="hm-card grid min-h-64 place-items-center p-8 text-sm text-muted-foreground">
        <div className="inline-flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Загружаю данные…
        </div>
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
        <DashboardHeader profileName={data.profile.display_name} />
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

  if (isDemoDataSource(data.dashboard.source_label)) {
    return (
      <div className="space-y-6">
        <DashboardHeader profileName={data.profile.display_name} />
        {data.completion && <DashboardProfileContextCard completion={data.completion} />}
        <div className="hm-card border-warning/30 bg-warning/5 p-6 md:p-8">
          <h2 className="font-display text-xl font-semibold">Демонстрационная сводка скрыта</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Ранее созданные демонстрационные показатели не показываются как ваши медицинские данные.
            Используйте подтверждённые сведения профиля и показатели.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              to="/app/profile"
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-elegant hover:opacity-90"
            >
              Открыть профиль <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/app/labs"
              className="inline-flex items-center gap-1.5 rounded-xl border border-border px-4 py-2 text-sm font-medium hover:bg-muted/40"
            >
              Открыть показатели
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const summary = data.dashboard.summary;
  const priorities = data.dashboard.priorities;

  return (
    <div className="space-y-6">
      <DashboardHeader
        profileName={data.profile.display_name}
        createdAt={data.dashboard.created_at}
      />

      {data.completion && <DashboardProfileContextCard completion={data.completion} />}

      <section className="hm-card p-6 md:p-8">
        <div className="flex items-start gap-4">
          <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-primary/20 bg-primary/10">
            <BarChart3 className="h-6 w-6 text-primary" />
          </div>
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground">
              Индекс сохранённой сводки
            </div>
            <div className="mt-1 font-display text-3xl font-semibold text-primary">
              {summary.observationIndex}
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Это значение из сохранённой сводки. Health Compass не добавляет к нему диагноз или
              медицинский вывод на этом экране.
            </p>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat
          icon={Bed}
          label="Средний сон"
          value={`${summary.avgSleep.hours} ч ${summary.avgSleep.minutes} мин`}
        />
        <Stat
          icon={Gauge}
          label="Ночей короче 7 часов"
          value={`${summary.shortNightsPct}%`}
        />
        <Stat
          icon={CalendarClock}
          label="Дней активности"
          value={fmt.format(summary.activeDays)}
        />
        <Stat
          icon={Dna}
          label="Генетических позиций"
          value={fmt.format(summary.geneticPositions)}
        />
      </div>

      {priorities.length > 0 && (
        <section className="hm-card p-5 md:p-6">
          <h2 className="font-display text-lg font-semibold tracking-tight">
            Приоритеты из сохранённой сводки
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Это записи сохранённой сводки, а не диагноз или назначение Health Compass.
          </p>
          <ul className="mt-4 grid gap-3 md:grid-cols-2">
            {priorities.map((priority) => {
              const Icon = priorityIcon[priority.priority];
              return (
                <li key={priority.id} className="rounded-xl border border-border/60 bg-surface-2/60 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div
                        className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg border ${priorityStyles[priority.priority]}`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="font-medium">{priority.title}</div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          {priority.description}
                        </div>
                      </div>
                    </div>
                    <span
                      className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${priorityStyles[priority.priority]}`}
                    >
                      {priorityLabel[priority.priority]}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}

function DashboardHeader({
  profileName,
  createdAt,
}: {
  profileName: string;
  createdAt?: string;
}) {
  return (
    <header>
      <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Главная</h1>
      <p className="mt-1 text-sm text-muted-foreground">Профиль: {profileName}</p>
      {createdAt && (
        <p className="mt-1 text-xs text-muted-foreground">
          Сводка обновлена {new Date(createdAt).toLocaleString("ru-RU")}
        </p>
      )}
    </header>
  );
}
