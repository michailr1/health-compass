import { ArrowRight, CheckCircle2, CircleDashed } from "lucide-react";
import { Link } from "react-router-dom";

import type { ProfileCompletionSummary } from "@/lib/api";

export function profileContextMessage(completion: ProfileCompletionSummary) {
  if (completion.progress_percent === 100) {
    return "Основные разделы профиля просмотрены. Health Compass может учитывать сохранённый контекст в отчётах и консультациях.";
  }
  if (completion.completed_sections === 0) {
    return "Профиль пока почти не заполнен. Дашборд продолжит работать, но персонализация отчётов и консультаций будет ограничена.";
  }
  return "Часть контекста уже учтена. Дополнение профиля может сделать отчёты и консультации точнее, но не обязательно для работы сервиса.";
}

export function DashboardProfileContextCard({ completion }: { completion: ProfileCompletionSummary }) {
  const next = completion.sections.find((section) => section.key === completion.next_section);

  return (
    <section className="hm-card p-5 md:p-6" aria-labelledby="dashboard-profile-context-title">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2">
            {completion.progress_percent === 100 ? (
              <CheckCircle2 className="h-5 w-5 text-success" aria-hidden="true" />
            ) : (
              <CircleDashed className="h-5 w-5 text-primary" aria-hidden="true" />
            )}
            <h2 id="dashboard-profile-context-title" className="font-display text-lg font-semibold">
              Контекст профиля
            </h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {profileContextMessage(completion)}
          </p>
        </div>

        <div className="shrink-0 md:text-right">
          <div className="font-display text-2xl font-semibold">{completion.progress_percent}%</div>
          <div className="text-xs text-muted-foreground">
            {completion.completed_sections} из {completion.total_sections} разделов
          </div>
        </div>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${completion.progress_percent}%` }}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {next ? (
          <Link
            to={`/app/profile${next.next_action}`}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-border px-4 py-2 text-sm font-medium hover:bg-muted/40"
          >
            Продолжить: {next.title} <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        ) : (
          <Link
            to="/app/profile"
            className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-border px-4 py-2 text-sm font-medium hover:bg-muted/40"
          >
            Открыть профиль <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        )}
        <span className="text-xs text-muted-foreground">
          Отложенные разделы не требуют немедленного заполнения.
        </span>
      </div>
    </section>
  );
}
