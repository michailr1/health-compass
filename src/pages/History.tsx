import { ArrowRight, Beaker, FileText, HeartPulse } from "lucide-react";
import { Link } from "react-router-dom";

const historySections = [
  {
    to: "/app/labs",
    title: "Показатели и их изменения",
    description:
      "Активные значения, исправления и записи, убранные из активного использования, с сохранённой защищённой историей.",
    icon: Beaker,
  },
  {
    to: "/app/documents",
    title: "Анализы",
    description:
      "Загруженные файлы, этапы проверки и переход к распознанным результатам, когда обработка доступна.",
    icon: FileText,
  },
  {
    to: "/app/profile",
    title: "Профиль здоровья",
    description:
      "Текущие сведения о здоровье и доступная история изменений клинического контекста.",
    icon: HeartPulse,
  },
];

export default function History() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">История</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Переходите к реальным данным профиля. Демонстрационные отчёты здесь не показываются.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {historySections.map((section) => {
          const Icon = section.icon;
          return (
            <Link
              key={section.to}
              to={section.to}
              className="hm-card group flex min-h-40 flex-col justify-between p-5 transition hover:border-primary/40"
            >
              <div>
                <div className="grid h-10 w-10 place-items-center rounded-xl border border-primary/20 bg-primary/10">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <h2 className="mt-4 font-display text-lg font-semibold">{section.title}</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{section.description}</p>
              </div>
              <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
                Открыть <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
