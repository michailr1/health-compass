import { reportHistory } from "@/data/demo";
import { useState } from "react";
import { FileText, Calendar, ChevronRight, X } from "lucide-react";

export default function History() {
  const [openId, setOpenId] = useState<string | null>(null);
  const open = reportHistory.find((r) => r.id === openId) ?? null;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">История отчётов</h1>
        <p className="mt-1 text-sm text-muted-foreground">Версии сводного отчёта. Открытие — демо-запись без реальных документов.</p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {reportHistory.map((r) => (
          <button
            key={r.id}
            onClick={() => setOpenId(r.id)}
            className="hm-card group p-5 text-left transition hover:border-primary/40"
          >
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Calendar className="h-3.5 w-3.5" /> {r.date}
              <span className="ml-auto rounded-full border border-border/70 bg-surface-2 px-2 py-0.5 font-mono text-[10px]">
                {r.version}
              </span>
            </div>
            <div className="mt-2 flex items-start gap-2">
              <FileText className="mt-0.5 h-4 w-4 text-primary" />
              <div>
                <div className="font-medium">{r.title}</div>
                <div className="mt-1 text-sm text-muted-foreground">{r.summary}</div>
              </div>
            </div>
            <div className="mt-4 inline-flex items-center gap-1 text-xs text-primary opacity-80 group-hover:opacity-100">
              Открыть запись <ChevronRight className="h-3.5 w-3.5" />
            </div>
          </button>
        ))}
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-background/70 p-3 backdrop-blur-sm md:items-center md:p-6"
          onClick={() => setOpenId(null)}
        >
          <div
            className="hm-card w-full max-w-2xl p-6 shadow-elegant animate-fade-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs text-muted-foreground">{open.date} · версия {open.version}</div>
                <h2 className="mt-1 font-display text-xl font-semibold tracking-tight">{open.title}</h2>
              </div>
              <button
                onClick={() => setOpenId(null)}
                className="rounded-lg border border-border p-1.5 text-muted-foreground hover:text-foreground"
                aria-label="Закрыть"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{open.summary}</p>
            <ul className="mt-4 space-y-2">
              {open.highlights.map((h, i) => (
                <li key={i} className="flex items-start gap-2 rounded-xl border border-border/60 bg-surface-2/50 p-3 text-sm">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                  <span>{h}</span>
                </li>
              ))}
            </ul>
            <div className="mt-5 rounded-xl border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
              Демонстрационная запись — исходные медицинские файлы в боевой версии не отдаются напрямую в браузер.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
