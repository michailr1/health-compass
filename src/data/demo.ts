// Demo dataset for HealthMonitor.
// NOTE: All values are synthetic / de-identified. No real PII, VCF, or clinical files.
// Structure is intentionally API-shaped so it can be replaced by real fetchers later.

export type ConfidenceLevel = "low" | "medium" | "high";
export type ProcessingStatus = "processed" | "partial" | "pending";
export type Priority = "high" | "medium" | "info";

export interface DashboardSummary {
  observationIndex: number;
  avgSleep: { hours: number; minutes: number };
  shortNightsPct: number;
  activeDays: number;
  geneticPositions: number;
}

export interface PriorityItem {
  id: string;
  title: string;
  description: string;
  priority: Priority;
}

export interface OuraMetric {
  key: string;
  label: string;
  unit: string;
  deltaPct: number; // last30 vs first30 (indexed to 100)
  series: Array<{ day: number; first30: number; last30: number }>;
}

export interface GeneticMarker {
  marker: string;
  rsid: string;
  genotype: string;
  area: string;
  interpretation: string;
  confidence: ConfidenceLevel;
}

export interface ActionItem {
  id: string;
  title: string;
  detail: string;
  bucket: "now" | "1_3m" | "later";
}

export interface DataSource {
  id: string;
  name: string;
  description: string;
  status: ProcessingStatus;
  version: string;
  updatedAt: string;
}

export interface ReportVersion {
  id: string;
  version: string;
  date: string;
  title: string;
  summary: string;
  highlights: string[];
}

export const dashboardSummary: DashboardSummary = {
  observationIndex: 72,
  avgSleep: { hours: 6, minutes: 39 },
  shortNightsPct: 60,
  activeDays: 288,
  geneticPositions: 630_790,
};

export const priorities: PriorityItem[] = [
  {
    id: "fvl",
    title: "Подтвердить предполагаемый Factor V Leiden",
    description:
      "Маркер F5 rs6025 требует клинического подтверждения (коагулограмма, консультация гематолога).",
    priority: "high",
  },
  {
    id: "sleep",
    title: "Улучшить продолжительность и регулярность сна",
    description: "60% ночей короче 7 часов. Цель — стабильные 7ч 30мин с постоянным окном отхода ко сну.",
    priority: "medium",
  },
  {
    id: "activity",
    title: "Вернуть повседневную активность",
    description: "Шаги −39% за последние 30 дней. Восстановить базовый объём NEAT.",
    priority: "medium",
  },
  {
    id: "cardio",
    title: "Собрать кардиометаболический baseline",
    description: "Липидный профиль, глюкоза натощак, HbA1c, АД в динамике — для последующего сравнения.",
    priority: "info",
  },
];

// Helper: build a smooth indexed series (first30 = 100 baseline)
function buildSeries(finalDelta: number, noise = 3): OuraMetric["series"] {
  const days = 30;
  return Array.from({ length: days }, (_, i) => {
    const t = i / (days - 1);
    const trend = 100 + finalDelta * t;
    const wobble = Math.sin(i * 0.9) * noise * 0.5;
    return {
      day: i + 1,
      first30: Math.round(100 + Math.sin(i * 0.7) * noise),
      last30: Math.round(trend + wobble),
    };
  });
}

export const ouraMetrics: OuraMetric[] = [
  { key: "hrv", label: "HRV", unit: "индекс", deltaPct: 23, series: buildSeries(23, 4) },
  { key: "readiness", label: "Readiness", unit: "индекс", deltaPct: 15, series: buildSeries(15, 3) },
  { key: "rhr", label: "Ночной пульс", unit: "индекс", deltaPct: -5, series: buildSeries(-5, 2) },
  { key: "steps", label: "Шаги", unit: "индекс", deltaPct: -39, series: buildSeries(-39, 6) },
];

export const geneticMarkers: GeneticMarker[] = [
  {
    marker: "F5", rsid: "rs6025", genotype: "C/C", area: "Свёртываемость крови",
    interpretation: "Предполагаемый Factor V Leiden — требует клинического подтверждения.",
    confidence: "medium",
  },
  {
    marker: "F2", rsid: "rs1799963", genotype: "G/G", area: "Свёртываемость крови",
    interpretation: "Референсный генотип. Дополнительных сигналов по протромбину не обнаружено.",
    confidence: "high",
  },
  {
    marker: "MTHFR", rsid: "rs1801133", genotype: "G/A", area: "Фолатный обмен",
    interpretation: "Гетерозигота. Обычно клинически незначима вне контекста дефицита фолата/B12.",
    confidence: "high",
  },
  {
    marker: "FTO", rsid: "rs9939609", genotype: "A/A", area: "Метаболизм / вес",
    interpretation: "Ассоциирован с более высокой склонностью к набору веса. Управляется образом жизни.",
    confidence: "medium",
  },
  {
    marker: "TCF7L2", rsid: "rs7903146", genotype: "C/T", area: "Углеводный обмен",
    interpretation: "Небольшое повышение риска СД2. Полезен ранний метаболический baseline.",
    confidence: "high",
  },
  {
    marker: "SLCO1B1", rsid: "rs4149056", genotype: "T/C", area: "Фармакогенетика (статины)",
    interpretation: "Промежуточный транспорт. Учитывать при подборе статинов совместно с врачом.",
    confidence: "high",
  },
  {
    marker: "ACTN3", rsid: "rs1815739", genotype: "T/C", area: "Мышцы / выносливость",
    interpretation: "Смешанный профиль скорость/выносливость. Клинически незначимо.",
    confidence: "high",
  },
  {
    marker: "LCT", rsid: "rs4988235", genotype: "G/A", area: "Толерантность к лактозе",
    interpretation: "Персистенция лактазы вероятна. Толерантность к молочному ожидаема.",
    confidence: "high",
  },
  {
    marker: "APOE", rsid: "—", genotype: "не определён", area: "Липиды / нейродегенерация",
    interpretation: "Позиции не покрыты чипом. Требуется отдельный анализ.",
    confidence: "low",
  },
];

export const actionPlan: ActionItem[] = [
  { id: "a1", bucket: "now", title: "Консультация гематолога", detail: "Обсудить F5 rs6025 и необходимость коагулограммы." },
  { id: "a2", bucket: "now", title: "Стабильное окно сна", detail: "Отбой в диапазоне 23:00–23:30 минимум 5 ночей в неделю." },
  { id: "a3", bucket: "now", title: "Базовые анализы", detail: "Липидный профиль, глюкоза, HbA1c, ферритин, B12, гомоцистеин." },
  { id: "b1", bucket: "1_3m", title: "Аэробный объём", detail: "150–180 мин Zone 2 в неделю; шаги 8–10 тыс./день." },
  { id: "b2", bucket: "1_3m", title: "Силовой минимум", detail: "2 короткие силовые сессии в неделю (низ/верх)." },
  { id: "b3", bucket: "1_3m", title: "Повтор Oura-снапшота", detail: "Сравнить HRV / RHR / Readiness через 60 дней." },
  { id: "c1", bucket: "later", title: "Кардиочек", detail: "АД-мониторинг 7 дней, ЭКГ покоя при показаниях." },
  { id: "c2", bucket: "later", title: "Расширенная генетика", detail: "Дозаказ APOE и панели, не покрытых SNP-чипом." },
  { id: "c3", bucket: "later", title: "Годовой обзор", detail: "Свести Oura + лабораторию + генетику в единый годовой отчёт." },
];

export const dataSources: DataSource[] = [
  {
    id: "genotek",
    name: "Genotek SNP-array",
    description: "Демо-снапшот: 630 790 позиций после QC, обезличенный набор.",
    status: "processed",
    version: "v1.2",
    updatedAt: "2026-05-18",
  },
  {
    id: "oura",
    name: "Oura export",
    description: "Ежедневные метрики HRV / RHR / Readiness / шаги за 288 дней.",
    status: "processed",
    version: "v3.4",
    updatedAt: "2026-06-30",
  },
  {
    id: "integral",
    name: "Интегральный отчёт",
    description: "Сведение генетики и физиологии в приоритеты и план действий.",
    status: "partial",
    version: "v0.9",
    updatedAt: "2026-07-02",
  },
];

export const reportHistory: ReportVersion[] = [
  {
    id: "r-2026-07",
    version: "v0.9",
    date: "2026-07-02",
    title: "Интегральный отчёт — черновик",
    summary: "Сведены Oura-снапшот и SNP-чип. Добавлен приоритет по F5.",
    highlights: [
      "Приоритет: клиническое подтверждение F5",
      "HRV +23% за последние 30 дней",
      "Шаги −39% — сигнал к восстановлению активности",
    ],
  },
  {
    id: "r-2026-05",
    version: "v0.6",
    date: "2026-05-20",
    title: "Генетический baseline",
    summary: "Первичный разбор SNP-чипа, 8 маркеров с интерпретацией.",
    highlights: ["Добавлены F5, F2, MTHFR, FTO, TCF7L2, SLCO1B1, ACTN3, LCT"],
  },
  {
    id: "r-2026-03",
    version: "v0.3",
    date: "2026-03-11",
    title: "Oura-snapshot",
    summary: "Первый срез 30 дней Oura для последующего сравнения.",
    highlights: ["Индексирование к 100 для сопоставимости"],
  },
];
