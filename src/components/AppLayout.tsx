import { useQuery } from "@tanstack/react-query";
import {
  ChevronRight,
  CirclePlus,
  HeartPulse,
  History,
  House,
  LogOut,
  Menu,
  MessageCircleMore,
  type LucideIcon,
} from "lucide-react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";
import { apiGet, type HealthProfile } from "@/lib/api";
import {
  MORE_NAVIGATION,
  PRIMARY_NAVIGATION,
  type PrimaryNavigationId,
  type ProductNavigationItem,
} from "@/lib/productUx";

const navIcons: Record<PrimaryNavigationId, LucideIcon> = {
  home: House,
  history: History,
  add: CirclePlus,
  assistant: MessageCircleMore,
  more: Menu,
};

const legacySecondaryRoutes = ["/app/genetics", "/app/plan", "/app/oura"];

export function resolveProfileDisplayName(
  profiles: HealthProfile[] | undefined,
  accountDisplayName: string | null | undefined,
  email: string | null | undefined,
): string {
  return profiles?.[0]?.display_name || accountDisplayName || email || "Пользователь";
}

function isPrimaryNavigationActive(item: ProductNavigationItem, pathname: string): boolean {
  if (item.id === "home") return pathname === "/app" || pathname === "/app/";
  if (item.id === "more") {
    return (
      pathname === item.to ||
      MORE_NAVIGATION.some((secondary) => pathname.startsWith(secondary.to)) ||
      legacySecondaryRoutes.some((route) => pathname.startsWith(route))
    );
  }
  return pathname === item.to || pathname.startsWith(`${item.to}/`);
}

export default function AppLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { data: profiles } = useQuery({
    queryKey: ["health-profiles", "layout"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
    enabled: Boolean(user),
  });
  const displayName = resolveProfileDisplayName(profiles, user?.display_name, user?.email);

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

          <nav aria-label="Основная навигация" className="mt-2 flex-1 space-y-1 px-3">
            {PRIMARY_NAVIGATION.map((item) => {
              const Icon = navIcons[item.id];
              const active = isPrimaryNavigationActive(item, location.pathname);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className={[
                    "group flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                  ].join(" ")}
                >
                  <Icon className="h-4 w-4 opacity-80 group-hover:opacity-100" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="border-t border-sidebar-border p-3">
            <div className="rounded-xl bg-sidebar-accent/60 p-1.5">
              <Link
                to="/app/profile"
                aria-label={`Открыть профиль здоровья: ${displayName}`}
                className="group block cursor-pointer rounded-lg border border-transparent px-2.5 py-2 transition-all hover:border-primary/25 hover:bg-sidebar-accent hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-sidebar-foreground transition-colors group-hover:text-primary">
                      {displayName}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
                    <div className="mt-1 text-[11px] font-medium text-primary">Профиль здоровья</div>
                  </div>
                  <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                </div>
              </Link>
              <button
                type="button"
                onClick={onLogout}
                className="mt-0.5 flex min-h-10 w-full items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
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
            <div className="flex items-center gap-2">
              <Link
                to="/app/profile"
                aria-label={`Открыть профиль здоровья: ${displayName}`}
                className="max-w-32 truncate rounded-md px-2 py-1.5 text-xs text-primary transition-colors hover:bg-primary/10"
              >
                {displayName}
              </Link>
              <button
                type="button"
                onClick={onLogout}
                aria-label="Выйти"
                className="grid h-9 w-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </header>

          <div className="mx-auto w-full max-w-6xl flex-1 space-y-5 px-4 pb-28 pt-5 md:px-8 md:pb-10 md:pt-8">
            <Outlet />
          </div>
        </main>
      </div>

      <nav
        aria-label="Основная навигация"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border/70 bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        <ul className="mx-auto grid max-w-lg grid-cols-5">
          {PRIMARY_NAVIGATION.map((item) => {
            const Icon = navIcons[item.id];
            const active = isPrimaryNavigationActive(item, location.pathname);
            return (
              <li key={item.to}>
                <Link
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className={[
                    "flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 py-2 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/60",
                    active ? "text-primary" : "text-muted-foreground",
                  ].join(" ")}
                >
                  <Icon className="h-5 w-5" />
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
