import { ArrowRight, MoonStar } from "lucide-react";
import { Link } from "react-router-dom";

export default function Oura() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Сон</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Данные сна будут объединяться по смыслу независимо от производителя устройства.
        </p>
      </header>

      <section className="hm-card p-6 md:p-8">
        <div className="grid h-12 w-12 place-items-center rounded-2xl border border-primary/20 bg-primary/10">
          <MoonStar className="h-6 w-6 text-primary" />
        </div>
        <h2 className="mt-5 font-display text-xl font-semibold">Данных сна пока нет</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Этот экран не показывает демонстрационные метрики как данные вашего профиля. Показатели сна появятся после запуска и подключения поддерживаемого источника.
        </p>
        <Link
          to="/app/sources"
          className="mt-5 inline-flex items-center gap-1.5 rounded-xl border border-border px-4 py-2 text-sm font-medium hover:bg-muted/40"
        >
          Открыть источники <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
