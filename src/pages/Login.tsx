import { Navigate } from "react-router-dom";
import { HeartPulse, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

export default function Login() {
  const { user, loading, signIn } = useAuth();

  if (!loading && user) return <Navigate to="/app" replace />;

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

        <div className="hm-card p-6 md:p-7">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Вход в кабинет</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Авторизация выполняется через защищённый серверный вход Authentik.
          </p>

          <Button
            type="button"
            disabled={loading}
            onClick={signIn}
            className="mt-6 w-full bg-gradient-primary text-primary-foreground hover:opacity-90"
          >
            Войти через Authentik
          </Button>

          <div className="mt-6 flex items-start gap-2 rounded-xl border border-primary/30 bg-primary/10 p-3 text-xs text-primary">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              Health Compass использует серверную сессию и HttpOnly cookie. Пароль не хранится в приложении.
            </div>
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          © Health Compass
        </p>
      </div>
    </div>
  );
}
