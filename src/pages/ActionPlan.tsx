import { actionPlan } from "@/data/demo";
import { Clock, CalendarRange, ArrowRight, Info } from "lucide-react";

const columns = [
  { key: "now" as const, label: "Сейчас", icon: Clock, tone: "text-primary" },
  { key: "1_3m" as const, label: "1–3 месяца", icon: CalendarRange, tone: "text-warning" },
  { key: "later" as const, label: "Далее", icon: ArrowRight, tone: "text-muted-foreground" },
];

export default function ActionPlan() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">План действий</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Информационный план, а <span className="text-foreground">не медицинское назначение</span>. Все решения принимаются с врачом.
        </p>
      </header>

      <div className="flex items-start gap-2 rounded-xl border border-primary/25 bg-primary/5 p-3 text-sm">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <div className="text-muted-foreground">
          Пункты сгруппированы по горизонту: срочные шаги, ближайшие 1–3 месяца и долгосрочные направления.
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {columns.map((col) => {
          const items = actionPlan.filter((a) => a.bucket === col.key);
          return (
            <section key={col.key} className="hm-card p-5">
              <div className="mb-4 flex items-center gap-2">
                <col.icon className={`h-4 w-4 ${col.tone}`} />
                <h2 className="font-display text-base font-semibold">{col.label}</h2>
                <span className="ml-auto text-xs text-muted-foreground">{items.length}</span>
              </div>
              <ul className="space-y-3">
                {items.map((a) => (
                  <li key={a.id} className="rounded-xl border border-border/60 bg-surface-2/50 p-3">
                    <div className="font-medium">{a.title}</div>
                    <div className="mt-1 text-sm text-muted-foreground">{a.detail}</div>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
