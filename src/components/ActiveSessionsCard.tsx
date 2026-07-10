import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Laptop, Loader2, RefreshCw, ShieldCheck, Smartphone, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";

export type AuthSessionSummary = {
  id: string;
  is_current: boolean;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  expires_at: string;
};

export function describeSessionAgent(userAgent: string | null) {
  if (!userAgent) return "Неизвестное устройство";
  const ua = userAgent.toLowerCase();
  const device = /iphone|ipad|android|mobile/.test(ua) ? "Мобильное устройство" : "Компьютер";
  let browser = "Браузер";
  if (ua.includes("edg/")) browser = "Microsoft Edge";
  else if (ua.includes("chrome/")) browser = "Google Chrome";
  else if (ua.includes("safari/") && !ua.includes("chrome/")) browser = "Safari";
  else if (ua.includes("firefox/")) browser = "Firefox";
  return `${device} · ${browser}`;
}

export function ActiveSessionsCard() {
  const queryClient = useQueryClient();
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["auth-sessions"],
    queryFn: () => apiGet<AuthSessionSummary[]>("/auth/sessions"),
  });

  const revokeMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      const response = await fetch(`/api/auth/sessions/${encodeURIComponent(sessionId)}`, {
        method: "DELETE",
        credentials: "include",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail ?? "Не удалось завершить сеанс");
      return payload as { current_session: boolean };
    },
    onSuccess: (payload) => {
      if (payload.current_session) {
        window.location.assign("/login");
        return;
      }
      setConfirmId(null);
      setMessage("Сеанс завершён.");
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ["auth-sessions"] });
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось завершить сеанс");
    },
  });

  const rotateMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/auth/sessions/current/rotate", {
        method: "POST",
        credentials: "include",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail ?? "Не удалось обновить сеанс");
      return payload;
    },
    onSuccess: () => {
      setMessage("Текущий сеанс безопасно обновлён. Старый токен больше не действует.");
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ["auth-sessions"] });
    },
    onError: (error) => {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось обновить сеанс");
    },
  });

  return (
    <section className="hm-card p-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="flex items-center gap-2 font-medium">
            <ShieldCheck className="h-4 w-4 text-primary" /> Активные сеансы
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Здесь показаны браузеры и устройства, где ваш аккаунт сейчас открыт. Незнакомый сеанс можно завершить.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={rotateMutation.isPending}
          onClick={() => rotateMutation.mutate()}
        >
          {rotateMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Обновить текущий сеанс
        </Button>
      </div>

      {message && <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-3 text-sm text-primary">{message}</div>}
      {errorMessage && <div className="mt-4 rounded-xl border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">{errorMessage}</div>}

      {query.isLoading && (
        <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Загружаем активные сеансы…
        </div>
      )}

      {query.error && <div className="mt-4 text-sm text-destructive">Не удалось загрузить активные сеансы.</div>}

      {query.data && (
        <div className="mt-5 space-y-3">
          {query.data.map((session) => {
            const Icon = /iphone|ipad|android|mobile/i.test(session.user_agent ?? "") ? Smartphone : Laptop;
            const confirming = confirmId === session.id;
            return (
              <article key={session.id} className="rounded-xl border border-border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-muted">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-medium">{describeSessionAgent(session.user_agent)}</h3>
                        {session.is_current && (
                          <span className="rounded-full bg-primary/10 px-2 py-1 text-xs text-primary">Текущий</span>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Создан {new Date(session.created_at).toLocaleString("ru-RU")}
                        {session.ip_address ? ` · IP ${session.ip_address}` : ""}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Истекает {new Date(session.expires_at).toLocaleString("ru-RU")}
                      </p>
                    </div>
                  </div>
                </div>

                {!confirming ? (
                  <Button
                    type="button"
                    variant="ghost"
                    className="mt-3 w-full text-destructive hover:text-destructive"
                    onClick={() => setConfirmId(session.id)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    {session.is_current ? "Выйти на этом устройстве" : "Завершить сеанс"}
                  </Button>
                ) : (
                  <div className="mt-3 space-y-2 rounded-xl border border-destructive/20 bg-destructive/5 p-3">
                    <p className="text-xs leading-5 text-muted-foreground">
                      {session.is_current
                        ? "Вы выйдете из аккаунта на этом устройстве."
                        : "Этот браузер или устройство потеряет доступ к аккаунту."}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        type="button"
                        variant="destructive"
                        disabled={revokeMutation.isPending}
                        onClick={() => revokeMutation.mutate(session.id)}
                      >
                        Подтвердить
                      </Button>
                      <Button type="button" variant="outline" onClick={() => setConfirmId(null)}>
                        Отмена
                      </Button>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
