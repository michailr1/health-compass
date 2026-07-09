import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity, Dna, LayoutDashboard, ListChecks, Database, History, LogOut, HeartPulse, KeyRound,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const nav = [
  { to: "/app", label: "Дашборд", icon: LayoutDashboard, end: true },
  { to: "/app/oura", label: "Oura", icon: Activity },
  { to: "/app/genetics", label: "Генетика", icon: Dna },
  { to: "/app/plan", label: "План", icon: ListChecks },
  { to: "/app/sources", label: "Источники", icon: Database },
  { to: "/app/history", label: "История", icon: History },
];

export default function AppLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const displayName = user?.display_name || user?.email || "Пользователь";

  async function onLogout() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen w-full bg-background text-foreground">
      <div className="flex min-h-screen w-full">
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar/80 backdrop-blur-md md:flex">
          <div className="flex items-center gap-2.5 px-5 py-5">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-primary shadow-elegant">
              <HeartPulse className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <div className="font-display text-base font-semibold tracking-tight">Health Compass</div>
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">private portal</div>
            </div>
          </div>

          <nav className="mt-2 flex-1 space-y-1 px-3">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  [
                    "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                  ].join(" ")
                }
              >
                <item.icon className="h-4 w-4 opacity-80 group-hover:opacity-100" />
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="border-t border-sidebar-border p-3">
            <div className="rounded-xl bg-sidebar-accent/60 px-3 py-2.5">
              <Link to="/app/profile" className="block rounded-lg hover:text-primary">
                <div className="truncate text-sm font-medium">{displayName}</div>
                <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
                <div className="mt-1 text-[11px] text-primary">Профиль здоровья</div>
              </Link>
              <Link
                to="/app/sign-in-methods"
                className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                <KeyRound className="h-3.5 w-3.5" /> Способы входа
              </Link>
              <button
                onClick={onLogout}
                className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                <LogOut className="h-3.5 w-3.5" /> Выйти
              </button>
            </div>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex items-center justify-between border-b border-border/70 bg-background/80 px-4 py-3 backdrop-blur md:hidden">
            <div className="flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-primary">
                <HeartPulse className="h-4 w-4 text-primary-foreground" />
              </div>
              <span className="font-display text-sm font-semibold">Health Compass</span>
            </div>
            <div className="flex items-center gap-3">
              <Link to="/app/sign-in-methods" aria-label="Способы входа" className="text-muted-foreground">
                <KeyRound className="h-4 w-4" />
              </Link>
              <Link to="/app/profile" className="max-w-32 truncate text-xs text-primary">
                {displayName}
              </Link>
              <button onClick={onLogout} className="text-xs text-muted-foreground">Выйти</button>
            </div>
          </header>

          <div className="mx-auto w-full max-w-6xl flex-1 space-y-5 px-4 pb-28 pt-5 md:px-8 md:pb-10 md:pt-8">
            <Outlet />
          </div>
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-border/70 bg-background/95 backdrop-blur md:hidden">
        <ul className="mx-auto grid max-w-lg grid-cols-6">
          {nav.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  [
                    "flex flex-col items-center gap-0.5 py-2.5 text-[10px]",
                    isActive ? "text-primary" : "text-muted-foreground",
                  ].join(" ")
                }
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
