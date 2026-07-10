import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Loader2, X } from "lucide-react";

import { apiGet, type ClinicalSectionKey, type ClinicalSuggestion } from "@/lib/api";

export type ClinicalSelection = {
  displayText: string;
  canonicalConceptId: string | null;
  source: "global" | "personal" | "free_text";
};

export function ClinicalTypeahead({
  profileId,
  section,
  placeholder,
  value,
  onChange,
}: {
  profileId: string;
  section: ClinicalSectionKey;
  placeholder: string;
  value: ClinicalSelection | null;
  onChange: (value: ClinicalSelection | null) => void;
}) {
  const inputId = useId();
  const listboxId = useId();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const normalized = query.trim();
  const { data, isFetching } = useQuery({
    queryKey: ["clinical-suggestions", profileId, section, normalized],
    queryFn: () => apiGet<{ items: ClinicalSuggestion[] }>(
      `/profiles/${profileId}/clinical-context/suggestions?section=${section}&q=${encodeURIComponent(normalized)}&limit=8`,
    ),
    enabled: normalized.length > 0 && value === null,
    staleTime: 30_000,
  });

  const options = data?.items ?? [];
  const exactMatch = options.some((item) => item.display_text.localeCompare(normalized, undefined, { sensitivity: "accent" }) === 0);
  const allOptions: Array<ClinicalSuggestion | { freeText: string }> = [
    ...options,
    ...(normalized && !exactMatch ? [{ freeText: normalized }] : []),
  ];

  const selectOption = (option: ClinicalSuggestion | { freeText: string }) => {
    if ("freeText" in option) {
      onChange({ displayText: option.freeText, canonicalConceptId: null, source: "free_text" });
    } else {
      onChange({
        displayText: option.display_text,
        canonicalConceptId: option.canonical_concept_id,
        source: option.source,
      });
    }
    setQuery("");
    setActiveIndex(0);
  };

  if (value) {
    return (
      <div className="flex max-w-full items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2.5 text-sm">
        <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <span className="min-w-0 flex-1 break-words">{value.displayText}</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="grid min-h-9 min-w-9 place-items-center rounded-lg text-muted-foreground hover:bg-muted"
          aria-label={`Удалить ${value.displayText}`}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <label className="block text-xs font-medium text-muted-foreground" htmlFor={inputId}>Новая запись</label>
      <div className="relative mt-1">
        <input
          id={inputId}
          autoFocus
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(0);
          }}
          onKeyDown={(event) => {
            if (!allOptions.length) return;
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActiveIndex((index) => (index + 1) % allOptions.length);
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActiveIndex((index) => (index - 1 + allOptions.length) % allOptions.length);
            } else if (event.key === "Enter") {
              event.preventDefault();
              selectOption(allOptions[activeIndex]);
            } else if (event.key === "Escape") {
              setQuery("");
            }
          }}
          placeholder={placeholder}
          autoComplete="off"
          role="combobox"
          aria-expanded={allOptions.length > 0}
          aria-controls={listboxId}
          aria-activedescendant={allOptions.length ? `${listboxId}-${activeIndex}` : undefined}
          className="min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2.5 pr-10 text-base sm:text-sm"
        />
        {isFetching && <Loader2 className="absolute right-3 top-3 h-4 w-4 animate-spin text-muted-foreground" aria-hidden="true" />}
      </div>
      {allOptions.length > 0 && (
        <div id={listboxId} role="listbox" className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-xl border border-border bg-popover p-1 shadow-lg">
          {allOptions.map((option, index) => {
            const isFreeText = "freeText" in option;
            const label = isFreeText ? `Добавить «${option.freeText}»` : option.display_text;
            return (
              <button
                id={`${listboxId}-${index}`}
                key={isFreeText ? `free-${option.freeText}` : `${option.source}-${option.canonical_concept_id ?? option.display_text}`}
                type="button"
                role="option"
                aria-selected={activeIndex === index}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectOption(option)}
                className={`block min-h-11 w-full rounded-lg px-3 py-2 text-left text-sm ${activeIndex === index ? "bg-muted" : "hover:bg-muted/60"}`}
              >
                <span className="block font-medium">{label}</span>
                {!isFreeText && option.qualifier && <span className="mt-0.5 block text-xs text-muted-foreground">{option.qualifier}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
