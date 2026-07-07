import { Navigate } from "react-router-dom";
import { HeartPulse, Mail, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.1c-.22-.66-.35-1.36-.35-2.1s.13-1.44.35-2.1V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06L5.84 9.9C6.71 7.3 9.14 5.38 12 5.38z" />
    </svg>
  );
}

export default function Login() {
  const { user, loading, signIn } = useAuth();

  if (!loading && user) return <Navigate to="/app" replace />;

  function signInWithGoogle() {
    window.location.assign("/auth/source/oauth/login/google/");
  }

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
            Войдите через Google или используйте резервный вход Authentik.
          </p>

          <div className="mt-6 space-y-3">
            <Button
              type="button"
              disabled={loading}
              onClick={signInWithGoogle}
              className="w-full bg-white text-slate-900 hover:bg-white/90"
            >
              <GoogleIcon />
              <span className="ml-2">Продолжить с Google</span>
            </Button>

            <Button
              type="button"
              disabled={loading}
              onClick={signIn}
              variant="outline"
              className="w-full"
            >
              <Mail className="h-4 w-4" />
              <span className="ml-2">Войти через Authentik</span>
            </Button>
          </div>

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
