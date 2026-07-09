import { Link, useSearchParams } from "react-router-dom";
import { HeartPulse, Link2, MailCheck, ShieldCheck, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AccountLink() {
  const [searchParams] = useSearchParams();
  const intent = searchParams.get("intent");
  const required = searchParams.get("required");
  const status = searchParams.get("status");
  const hasExistingDuplicates = status === "existing-duplicates";

  const googleConfirmationUrl = intent
    ? `/api/auth/link/google/start?intent_id=${encodeURIComponent(intent)}`
    : "/login";

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
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-primary/10 text-primary">
            {hasExistingDuplicates ? <TriangleAlert className="h-8 w-8" /> : <Link2 className="h-8 w-8" />}
          </div>

          <h1 className="mt-5 font-display text-2xl font-semibold tracking-tight">
            {hasExistingDuplicates ? "Найдены два существующих аккаунта" : "Связать способы входа?"}
          </h1>

          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {hasExistingDuplicates
              ? "Для этого адреса уже существуют разные профили. Мы не будем объединять их автоматически. Потребуется безопасная проверка обоих способов входа."
              : "Адрес уже связан с существующим профилем. Подтвердите второй способ входа, чтобы Google и ссылка по email всегда открывали один профиль."}
          </p>

          {!hasExistingDuplicates && required === "google" && (
            <div className="mt-6 space-y-3">
              <Button asChild className="w-full">
                <a href={googleConfirmationUrl}>Подтвердить через Google</a>
              </Button>
              <p className="text-xs text-muted-foreground">
                Новый профиль до завершения подтверждения не создаётся.
              </p>
            </div>
          )}

          {!hasExistingDuplicates && required === "email" && (
            <div className="mt-6 rounded-xl border border-primary/20 bg-primary/5 p-4 text-left">
              <div className="flex items-start gap-3">
                <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div>
                  <div className="text-sm font-medium">Подтвердите email</div>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Мы отправим специальную одноразовую ссылку с назначением link_email. Обычная ссылка для входа не сможет связать аккаунты.
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="mt-6 space-y-3">
            <Button asChild variant="outline" className="w-full">
              <Link to="/login">Отказаться и вернуться ко входу</Link>
            </Button>
          </div>

          <div className="mt-6 flex items-start gap-2 rounded-xl border border-primary/20 bg-primary/5 p-3 text-left text-xs text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>
              Совпадение email само по себе ничего не объединяет. Связывание завершится только после подтверждения второго способа.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
