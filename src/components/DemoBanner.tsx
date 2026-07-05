import { ShieldAlert } from "lucide-react";

export function DemoBanner() {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
      <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
      <span className="font-medium">Демонстрационные обезличенные данные.</span>
      <span className="text-warning/80">
        Не является медицинским заключением. Не для диагностики или лечения.
      </span>
    </div>
  );
}
