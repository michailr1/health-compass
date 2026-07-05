import { ouraMetrics } from "@/data/demo";
import { useState } from "react";
import {
  Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export default function Oura() {
  const [activeKey, setActiveKey] = useState(ouraMetrics[0].key);
  const active = ouraMetrics.find((m) => m.key === activeKey)!;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Oura — физиология</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Сравнение первых и последних 30 дней. Все ряды индексированы: <span className="text-foreground">первые 30 дней = 100</span>.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {ouraMetrics.map((m) => {
          const positive = (m.key === "rhr" ? m.deltaPct < 0 : m.deltaPct > 0);
          const isActive = m.key === activeKey;
          return (
            <button
              key={m.key}
              onClick={() => setActiveKey(m.key)}
              className={[
                "hm-card p-4 text-left transition-all",
                isActive ? "ring-1 ring-primary/60 border-primary/40" : "hover:border-primary/30",
              ].join(" ")}
            >
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{m.label}</div>
              <div className={`mt-1 font-display text-2xl font-semibold ${positive ? "text-success" : "text-warning"}`}>
                {m.deltaPct > 0 ? "+" : ""}{m.deltaPct}%
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground">Δ 30д vs 30д</div>
            </button>
          );
        })}
      </div>

      <section className="hm-card p-4 md:p-6">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="font-display text-lg font-semibold tracking-tight">{active.label}</h2>
          <span className="text-xs text-muted-foreground">индекс, база = 100</span>
        </div>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={active.series} margin={{ top: 10, right: 12, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="gFirst" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gLast" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.6} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 12,
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="first30" name="Первые 30 дней" stroke="hsl(var(--muted-foreground))" fill="url(#gFirst)" strokeWidth={2} />
              <Area type="monotone" dataKey="last30" name="Последние 30 дней" stroke="hsl(var(--primary))" fill="url(#gLast)" strokeWidth={2.2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <p className="text-xs text-muted-foreground">
        Индексирование сохраняет форму динамики и делает окна сопоставимыми независимо от абсолютных величин.
      </p>
    </div>
  );
}
