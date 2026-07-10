import type { SectionKey } from "@/components/ClinicalContextSection";

export type ClinicalAnswers = {
  onsetTiming?: "recent" | "long_ago" | "unknown";
  presencePattern?: "yes" | "resolved" | "recurring" | "unknown";
  reaction?: string;
  severity?: "mild" | "moderate" | "severe" | "unknown";
  currentUse?: "yes" | "no" | "unknown";
  startDate?: string;
  doseValue?: string;
  doseUnit?: string;
  frequencyText?: string;
  reasonText?: string;
};

function ChoiceGroup({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value?: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
            className={`min-h-10 rounded-xl border px-3 py-2 text-sm ${
              value === option.value ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function ClinicalClarifyingQuestions({
  section,
  answers,
  onChange,
}: {
  section: SectionKey;
  answers: ClinicalAnswers;
  onChange: (answers: ClinicalAnswers) => void;
}) {
  const set = <K extends keyof ClinicalAnswers>(key: K, value: ClinicalAnswers[K]) =>
    onChange({ ...answers, [key]: value });

  return (
    <div className="space-y-4 rounded-xl border border-border/70 bg-muted/20 p-3">
      <p className="text-sm font-medium">Несколько уточнений — можно пропустить</p>

      {section === "conditions" && (
        <>
          <ChoiceGroup
            label="Как давно это началось?"
            value={answers.onsetTiming}
            options={[
              { value: "recent", label: "Недавно" },
              { value: "long_ago", label: "Давно" },
              { value: "unknown", label: "Не знаю" },
            ]}
            onChange={(value) => set("onsetTiming", value as ClinicalAnswers["onsetTiming"])}
          />
          <ChoiceGroup
            label="Есть сейчас?"
            value={answers.presencePattern}
            options={[
              { value: "yes", label: "Да" },
              { value: "resolved", label: "Прошло" },
              { value: "recurring", label: "Повторяется" },
              { value: "unknown", label: "Не знаю" },
            ]}
            onChange={(value) => set("presencePattern", value as ClinicalAnswers["presencePattern"])}
          />
        </>
      )}

      {section === "allergies" && (
        <>
          <label className="block text-sm font-medium">
            Что происходит?
            <input
              value={answers.reaction ?? ""}
              onChange={(event) => set("reaction", event.target.value)}
              placeholder="Например, сыпь или тошнота"
              className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 text-base sm:text-sm"
            />
          </label>
          <ChoiceGroup
            label="Насколько выраженная реакция?"
            value={answers.severity}
            options={[
              { value: "mild", label: "Слабая" },
              { value: "moderate", label: "Средняя" },
              { value: "severe", label: "Сильная" },
              { value: "unknown", label: "Не знаю" },
            ]}
            onChange={(value) => set("severity", value as ClinicalAnswers["severity"])}
          />
          <ChoiceGroup
            label="Актуально сейчас?"
            value={answers.currentUse}
            options={[
              { value: "yes", label: "Да" },
              { value: "no", label: "Нет" },
              { value: "unknown", label: "Не знаю" },
            ]}
            onChange={(value) => set("currentUse", value as ClinicalAnswers["currentUse"])}
          />
        </>
      )}

      {(section === "medications" || section === "supplements") && (
        <>
          <ChoiceGroup
            label="Принимаете сейчас?"
            value={answers.currentUse}
            options={[
              { value: "yes", label: "Да" },
              { value: "no", label: "Нет" },
              { value: "unknown", label: "Не знаю" },
            ]}
            onChange={(value) => set("currentUse", value as ClinicalAnswers["currentUse"])}
          />
          <label className="block text-sm font-medium">
            Когда начали? <span className="font-normal text-muted-foreground">необязательно</span>
            <input
              type="date"
              value={answers.startDate ?? ""}
              onChange={(event) => set("startDate", event.target.value)}
              className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 text-base sm:text-sm"
            />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-sm font-medium">
              Доза
              <input
                inputMode="decimal"
                value={answers.doseValue ?? ""}
                onChange={(event) => set("doseValue", event.target.value)}
                className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 text-base sm:text-sm"
              />
            </label>
            <label className="block text-sm font-medium">
              Единица
              <input
                value={answers.doseUnit ?? ""}
                onChange={(event) => set("doseUnit", event.target.value)}
                placeholder="мг, мл"
                className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 text-base sm:text-sm"
              />
            </label>
          </div>
          <label className="block text-sm font-medium">
            Как часто?
            <input
              value={answers.frequencyText ?? ""}
              onChange={(event) => set("frequencyText", event.target.value)}
              placeholder="Например, один раз в день"
              className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 text-base sm:text-sm"
            />
          </label>
          {section === "medications" && (
            <label className="block text-sm font-medium">
              Для чего принимаете?
              <input
                value={answers.reasonText ?? ""}
                onChange={(event) => set("reasonText", event.target.value)}
                className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 text-base sm:text-sm"
              />
            </label>
          )}
        </>
      )}
    </div>
  );
}
