import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Link2, Loader2, Mail, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";

export type SignInMethod = {
  id: string;
  provider: "google" | "email" | string;
  label: string;
  verified: boolean;
  connected_at: string;
  last_seen_at: string | null;
  can_remove: boolean;
};

export const providerTitles: Record<string, string> = {
  google: "Google",
  email: "Email Magic Link",
};

export function getMissingProvider(methods: SignInMethod[]): "google" | "email" | null {
  const connected = new Set(methods.map((method) => method.provider));
  if (connected.has("google") && !connected.has("email")) return "email";
  if (connected.has("email") && !connected.has("google")) return "google";
  return null;
}

export default function SignInMethodsPage() {
  const { data = [], isLoading, error } = useQuery({
    queryKey: ["sign-in-methods"],
    queryFn: () => apiGet<SignInMethod[]>("/auth/identities"),
  });

  const missingProvider = getMissingProvider(data);

  return (
    <section className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm text-primary">
          <KeyRound className="h-4 w-4" /> Безопасность аккаунта
        </div>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">Способы входа</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Подключённые способы входа всегда открывают один и тот же профиль. Новый способ добавляется только после отдельного подтверждения владения им.
        </p>
      </div>

      {isLoading && (
        <div className="hm-card flex items-center gap-3 p-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Загружаем способы входа…
        </div>
      )}

      {error && (
        <div className="hm-card border-destructive/30 p-6 text-sm text-destructive">
          Не удалось загрузить способы входа.
        </div>
      )}

      {!isLoading && !error && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((method) => {
            const Icon = method.provider === "google" ? Link2 : Mail;
            return (
              <article key={method.id} className="hm-card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <h2 className="font-medium">{providerTitles[method.provider] ?? method.provider}</h2>
                      <p className="mt-1 break-all text-sm text-muted-foreground">{method.label}</p>
                    </div>
                  </div>
                  {method.verified && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-1 text-xs text-primary">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Подтверждён
                    </span>
                  )}
                </div>
                <div className="mt-4 text-xs text-muted-foreground">
                  Подключён {new Date(method.connected_at).toLocaleDateString("ru-RU")}
                </div>
                {!method.can_remove && (
                  <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
                    Это единственный способ входа. Его нельзя отключить.
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}

      {!isLoading && !error && missingProvider && (
        <div className="hm-card p-6">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div>
              <h2 className="font-display text-xl font-semibold">
                Подключить {providerTitles[missingProvider]}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Потребуется один раз подтвердить новый способ входа. Профиль и медицинские данные останутся прежними.
              </p>
            </div>
            <Button asChild>
              <a href={`/api/auth/link/settings/start?provider=${encodeURIComponent(missingProvider)}`}>
                Подключить
              </a>
            </Button>
          </div>
        </div>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm text-muted-foreground">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
        <span>
          Последний способ входа отключить нельзя. Удаление подключённого способа будет добавлено только вместе с повторным подтверждением личности.
        </span>
      </div>
    </section>
  );
}
