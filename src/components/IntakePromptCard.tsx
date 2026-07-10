import { useState } from "react";
import { HelpCircle, Loader2 } from "lucide-react";

export type IntakeDecision = "save_to_profile" | "analysis_only" | "defer";

export function IntakePromptCard({
  title,
  preview,
  why,
  onDecision,
  isPending = false,
}: {
  title: string;
  preview: string;
  why: string;
  onDecision: (decision: IntakeDecision) => void | Promise<void>;
  isPending?: boolean;
}) {
  const [showWhy, setShowWhy] = useState(false);

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm" aria-labelledby="intake-prompt-title">
      <h3 id="intake-prompt-title" className="font-display text-base font-semibold">{title}</h3>
      <p className="mt-2 text-sm leading-5 text-muted-foreground">{preview}</p>

      <button
        type="button"
        onClick={() => setShowWhy((value) => !value)}
        className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-xl px-2 text-sm font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={showWhy}
      >
        <HelpCircle className="h-4 w-4" aria-hidden="true" />
        Зачем это нужно
      </button>
      {showWhy && (
        <p className="mt-1 rounded-xl bg-muted/30 px-3 py-2 text-sm leading-5 text-muted-foreground">
          {why}
        </p>
      )}

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <button
          type="button"
          disabled={isPending}
          onClick={() => onDecision("save_to_profile")}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          Сохранить в профиль
        </button>
        <button
          type="button"
          disabled={isPending}
          onClick={() => onDecision("analysis_only")}
          className="min-h-11 rounded-xl border border-border px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          Только для этого анализа
        </button>
        <button
          type="button"
          disabled={isPending}
          onClick={() => onDecision("defer")}
          className="min-h-11 rounded-xl px-4 py-2 text-sm text-muted-foreground disabled:opacity-50 sm:col-span-2"
        >
          Не сейчас
        </button>
      </div>

      <p className="mt-3 text-xs leading-4 text-muted-foreground">
        «Только для этого анализа» не добавляет сведения в постоянный профиль.
      </p>
    </section>
  );
}
