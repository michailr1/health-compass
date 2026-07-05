import { geneticMarkers, type ConfidenceLevel } from "@/data/demo";

const confidenceLabel: Record<ConfidenceLevel, string> = {
  low: "низкая", medium: "средняя", high: "высокая",
};
const confidenceTone: Record<ConfidenceLevel, string> = {
  low: "border-destructive/30 bg-destructive/10 text-destructive",
  medium: "border-warning/30 bg-warning/10 text-warning",
  high: "border-success/30 bg-success/10 text-success",
};

export default function Genetics() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Генетика</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Демонстрационная выборка SNP-маркеров. Клинически значимые находки требуют подтверждения врачом.
        </p>
      </header>

      {/* Desktop table */}
      <div className="hm-card hidden overflow-hidden md:block">
        <table className="w-full text-sm">
          <thead className="bg-surface-2/60 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-4 py-3 text-left">Маркер</th>
              <th className="px-4 py-3 text-left">Генотип</th>
              <th className="px-4 py-3 text-left">Область</th>
              <th className="px-4 py-3 text-left">Интерпретация</th>
              <th className="px-4 py-3 text-left">Уверенность</th>
            </tr>
          </thead>
          <tbody>
            {geneticMarkers.map((m) => (
              <tr key={m.marker} className="border-t border-border/60 hover:bg-surface-2/40">
                <td className="px-4 py-3 align-top">
                  <div className="font-medium">{m.marker}</div>
                  <div className="font-mono text-xs text-muted-foreground">{m.rsid}</div>
                </td>
                <td className="px-4 py-3 align-top font-mono">{m.genotype}</td>
                <td className="px-4 py-3 align-top text-muted-foreground">{m.area}</td>
                <td className="px-4 py-3 align-top">{m.interpretation}</td>
                <td className="px-4 py-3 align-top">
                  <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] ${confidenceTone[m.confidence]}`}>
                    {confidenceLabel[m.confidence]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="grid gap-3 md:hidden">
        {geneticMarkers.map((m) => (
          <div key={m.marker} className="hm-card p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-medium">{m.marker}</div>
                <div className="font-mono text-xs text-muted-foreground">{m.rsid}</div>
              </div>
              <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] ${confidenceTone[m.confidence]}`}>
                {confidenceLabel[m.confidence]}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div><div className="text-muted-foreground">Генотип</div><div className="font-mono">{m.genotype}</div></div>
              <div><div className="text-muted-foreground">Область</div><div>{m.area}</div></div>
            </div>
            <p className="mt-3 text-sm">{m.interpretation}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
