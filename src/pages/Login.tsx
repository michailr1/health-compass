import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { HeartPulse, ShieldAlert, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export default function Login() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("demo@healthmonitor.local");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/app" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signIn(email, password);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen w-full place-items-center px-4 py-10">
      <div className="w-full max-w-md animate-fade-in">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-primary shadow-elegant">
            <HeartPulse className="h-6 w-6 text-primary-foreground" />
          </div>
          <div>
            <div className="font-display text-xl font-semibold tracking-tight">HealthMonitor</div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">personal health portal</div>
          </div>
        </div>

        <div className="hm-card p-6 md:p-7">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Вход в кабинет</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Демонстрационная mock-аутентификация. Данные никуда не отправляются.
          </p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email" type="email" autoComplete="email" value={email}
                onChange={(e) => setEmail(e.target.value)} required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password" type="password" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} required
              />
            </div>

            {error && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            <Button type="submit" disabled={busy} className="w-full bg-gradient-primary text-primary-foreground hover:opacity-90">
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Войти
            </Button>
          </form>

          <div className="mt-6 flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              Это демонстрационная авторизация — не для production. В боевой версии используется
              серверная аутентификация и приватный backend.
            </div>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          © HealthMonitor — обезличенные демонстрационные данные
        </p>
      </div>
    </div>
  );
}
