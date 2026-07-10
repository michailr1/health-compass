import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Clock3, Loader2 } from "lucide-react";

import { apiGet, type ProfileCompletionSummary } from "@/lib/api";

const STATE_LABELS = {
  complete: "Заполнено",
  deferred: "Отложено",
  incomplete: "Не завершено",
} as const;

export function ProfileCompletionCard({ profileId }: { profileId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["profile-completion", profileId],
    queryFn: () => apiGet<ProfileCompletionSummary>(`/profiles/${profileId}/completion`),
  });

  if (isLoading) {
    return (
      <section className="hm-card grid min-h-32 place-items-center" aria-label="Загрузка прогресса профиля">
        <Loader2 className="h-5 w-5 animate-spin" />
      </section>
    );
  }
  if (error || !data) return null;

  const next = data.sections.find((section) => section.key === data.next_section);

  return (
    <section className="hm-card p-5 md:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold">Заполнение профиля</h2>
          <p className="mt-1 text-sm leading-5 text-muted-foreground">
            Профиль можно заполнять постепенно. Все основные функции работают и при неполных данных, но персонализация будет ниже.
          </p>
        </div>
        <div className="shrink-0 text-left sm:text-right">
          <div className="text-2xl font-semibold">{data.progress_percent}%</div>
          <div className="text-xs text-muted-foreground">
            {data.completed_sections} из {data.total_sections} разделов
          </div>
        </div>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${data.progress_percent}%` }} />
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {data.sections.map((section) => {
          const Icon = section.state === "complete" ? CheckCircle2 : section.state === "deferred" ? Clock3 : CircleDashed;
          return (
            <a
              key={section.key}
              href={section.next_action}
              className="flex min-h-12 items-center gap-3 rounded-xl border border-border/70 px-3 py-2 hover:bg-muted/40"
            >
              <Icon className={`h-4 w-4 shrink-0 ${section.state === "complete" ? "text-primary" : "text-muted-foreground"}`} />
              <span className="min-w-0 flex-1 text-sm font-medium">{section.title}</span>
              <span className="text-xs text-muted-foreground">{STATE_LABELS[section.state]}</span>
            </a>
          );
        })}
      </div>

      {next && (
        <a
          href={next.next_action}
          className="mt-4 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground sm:w-auto"
        >
          Продолжить: {next.title}
        </a>
      )}
    </section>
  );
}
