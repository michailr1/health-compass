import { Link, useSearchParams } from "react-router-dom";
import { HeartPulse, Link2Off, Mail, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function MagicLinkStatus() {
  const [searchParams] = useSearchParams();
  const status = searchParams.get("status");
  const isInvalid = status === "invalid" || status === "expired";

  return (
    <div className="grid min-h-screen w-full place-items-center px-4 py-10">
      <div className="w-full max-w-md animate-fade-in">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-primary shadow-elegant">
            <HeartPulse className="h-6 w-6 text-primary-foreground" />
          </div>
          <div>
            <div className="font-display text-xl font-semibold tracking-tight">Health Compass</div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">personal health portal</div>
          </div>
        </div>

        <div className="hm-card p-6 text-center md:p-8">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-amber-500/10 text-amber-600">
            <Link2Off className="h-8 w-8" />
          </div>

          <h1 className="mt-5 font-display text-2xl font-semibold tracking-tight">
            {isInvalid ? "Ссылка больше не действует" : "Не удалось открыть ссылку"}
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Эта ссылка уже была использована, истекла или была заменена новой. Для безопасности ссылки для входа работают только один раз.
          </p>

          <div className="mt-6 space-y-3">
            <Button asChild className="w-full">
              <Link to="/login">
                <Mail className="h-4 w-4" />
                <span className="ml-2">Получить новую ссылку</span>
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full">
              <Link to="/">Вернуться на главную</Link>
            </Button>
          </div>

          <div className="mt-6 flex items-start gap-2 rounded-xl border border-primary/20 bg-primary/5 p-3 text-left text-xs text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>Повторное использование ссылки блокируется, чтобы защитить вашу учётную запись.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
