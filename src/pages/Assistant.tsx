import { ArrowRight, MessageCircleMore, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

export default function Assistant() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Ассистент</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Объяснения по данным здоровья появятся только после отдельного этапа проверки безопасности и источников.
        </p>
      </header>

      <section className="hm-card p-6 md:p-8">
        <div className="grid h-12 w-12 place-items-center rounded-2xl border border-primary/20 bg-primary/10">
          <MessageCircleMore className="h-6 w-6 text-primary" />
        </div>
        <h2 className="mt-5 font-display text-xl font-semibold">Ассистент пока не включён</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Здесь не показывается фиктивный чат и не создаются медицинские ответы без подтверждённых данных.
          До запуска ассистента можно заполнить профиль и проверить уже подтверждённые показатели.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            to="/app/profile"
            className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-elegant hover:opacity-90"
          >
            Открыть профиль <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            to="/app/labs"
            className="inline-flex items-center gap-1.5 rounded-xl border border-border px-4 py-2 text-sm font-medium hover:bg-muted/40"
          >
            Открыть показатели
          </Link>
        </div>
      </section>

      <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-muted/20 p-4 text-sm text-muted-foreground">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <p>
          Будущий ассистент должен отделять факты от интерпретаций и показывать источники каждого содержательного ответа.
        </p>
      </div>
    </div>
  );
}
