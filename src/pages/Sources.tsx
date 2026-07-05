import { dataSources, type ProcessingStatus } from "@/data/demo";
import { Database, CheckCircle2, Clock3, CircleDashed } from "lucide-react";

const statusMeta: Record<ProcessingStatus, { label: string; tone: string; Icon: React.ComponentType<{ className?: string }> }> = {
  processed: { label: "Обработано", tone: "border-success/30 bg-success/10 text-success", Icon: CheckCircle2 },
  partial: { label: "Частично", tone: "border-warning/30 bg-warning/10 text-warning", Icon: Clock3 },
  pending: { label: "В очереди", tone: "border-border bg-muted/40 text-muted-foreground", Icon: CircleDashed },
};

export default function Sources() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Источники данных</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          В демо-версии данные хранятся локально. В боевой версии — приватный backend, без прямой отдачи исходных файлов.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        {dataSources.map((s) => {
          const m = statusMeta[s.status];
          return (
            <div key={s.id} className="hm-card p-5">
              <div className="flex items-center gap-2">
                <div className="grid h-9 w-9 place-items-center rounded-xl border border-border bg-surface-2">
                  <Database className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs text-muted-foreground">версия {s.version} · {s.updatedAt}</div>
                </div>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">{s.description}</p>
              <div className="mt-4 flex items-center justify-between">
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] ${m.tone}`}>
                  <m.Icon className="h-3 w-3" /> {m.label}
                </span>
                <span className="text-[11px] uppercase tracking-wider text-muted-foreground">demo mock</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
