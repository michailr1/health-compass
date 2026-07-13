import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FilePlus2, HeartPulse, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

import { apiGet, type HealthProfile } from "@/lib/api";
import { getDocumentIntakeCapabilities } from "@/lib/documentApi";

export default function AddData() {
  const { data: profiles, isLoading: profilesLoading } = useQuery({
    queryKey: ["health-profiles", "add-data"],
    queryFn: () => apiGet<HealthProfile[]>("/profiles"),
  });
  const profile = profiles?.[0] ?? null;
  const { data: capabilities, isLoading: capabilitiesLoading } = useQuery({
    queryKey: ["document-intake-capabilities", profile?.id],
    queryFn: () => getDocumentIntakeCapabilities(profile!.id),
    enabled: Boolean(profile),
  });

  if (profilesLoading) {
    return (
      <div className="hm-card grid min-h-48 place-items-center p-8 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Загружаю доступные действия…
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Добавить</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Здесь показаны только действия, которые можно выполнить в текущей версии.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Link
          to="/app/profile"
          className="hm-card group flex min-h-40 flex-col justify-between p-5 transition hover:border-primary/40"
        >
          <div>
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-primary/20 bg-primary/10">
              <HeartPulse className="h-5 w-5 text-primary" />
            </div>
            <h2 className="mt-4 font-display text-lg font-semibold">
              {profile ? "Дополнить профиль здоровья" : "Создать профиль здоровья"}
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Добавьте основные сведения, состояния, лекарства и другой медицинский контекст.
            </p>
          </div>
          <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
            Открыть профиль <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </span>
        </Link>

        <Link
          to="/app/documents"
          className="hm-card group flex min-h-40 flex-col justify-between p-5 transition hover:border-primary/40"
        >
          <div>
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-primary/20 bg-primary/10">
              <FilePlus2 className="h-5 w-5 text-primary" />
            </div>
            <h2 className="mt-4 font-display text-lg font-semibold">
              {capabilities?.upload_enabled ? "Загрузить анализы" : "Анализы"}
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              {capabilitiesLoading
                ? "Проверяю доступность загрузки для профиля."
                : capabilities?.upload_enabled
                  ? "Добавьте PDF или фото результатов анализов для последующей проверки и подтверждения."
                  : "Загрузка временно недоступна. В разделе можно увидеть текущее состояние и ранее добавленные анализы."}
            </p>
          </div>
          <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
            {capabilities?.upload_enabled ? "Перейти к загрузке" : "Открыть раздел"}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </span>
        </Link>
      </div>
    </div>
  );
}
