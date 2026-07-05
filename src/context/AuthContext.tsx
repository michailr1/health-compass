import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

// DEMO-ONLY mock auth. Do NOT use in production.
// Real deployment must use server-side auth with a private backend.

interface DemoUser {
  email: string;
  displayName: string;
}

interface AuthContextValue {
  user: DemoUser | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = "hm.demo.user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<DemoUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setUser(JSON.parse(raw));
    } catch {}
    setLoading(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async signIn(email, password) {
        // Mock: accept anything non-empty. Do not send anywhere.
        await new Promise((r) => setTimeout(r, 350));
        if (!email || !password) throw new Error("Введите email и пароль");
        const u: DemoUser = { email, displayName: "Демо-пациент" };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(u));
        setUser(u);
      },
      signOut() {
        localStorage.removeItem(STORAGE_KEY);
        setUser(null);
      },
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
