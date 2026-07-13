import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import { MORE_NAVIGATION } from "@/lib/productUx";

export default function More() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Ещё</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Дополнительные разделы данных, источники и настройки аккаунта.
        </p>
      </header>

      <div className="grid gap-3 md:grid-cols-2">
        {MORE_NAVIGATION.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="hm-card group flex min-h-28 items-center justify-between gap-4 p-5 transition hover:border-primary/40"
          >
            <div>
              <h2 className="font-medium">{item.label}</h2>
              <p className="mt-1 text-sm leading-5 text-muted-foreground">{item.description}</p>
            </div>
            <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
          </Link>
        ))}
      </div>
    </div>
  );
}
