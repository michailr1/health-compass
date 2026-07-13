import { Database, ShieldCheck } from "lucide-react";

export default function Sources() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Источники</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Здесь будут находиться устройства и интеграции, которые передают данные в Health Compass.
        </p>
      </header>

      <section className="hm-card p-6 md:p-8">
        <div className="grid h-12 w-12 place-items-center rounded-2xl border border-primary/20 bg-primary/10">
          <Database className="h-6 w-6 text-primary" />
        </div>
        <h2 className="mt-5 font-display text-xl font-semibold">Подключённых источников пока нет</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Кнопка подключения появится только после запуска реальной интеграции. Сейчас этот раздел не показывает демонстрационные устройства и не предлагает действие, которое нельзя завершить.
        </p>
      </section>

      <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-muted/20 p-4 text-sm text-muted-foreground">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <p>
          Oura и другие поддерживаемые сервисы будут управляться здесь как источники данных, а не как отдельные разделы основной навигации.
        </p>
      </div>
    </div>
  );
}
