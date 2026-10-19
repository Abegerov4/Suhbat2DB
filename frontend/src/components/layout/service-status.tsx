"use client";

import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";

/** Доступность бэкенда: точка + подпись (цвет — не единственный признак). */
export function ServiceStatus({ className }: { className?: string }) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const r = await fetch("/api/health", { cache: "no-store" });
      if (!r.ok) throw new Error(String(r.status));
      return true;
    },
    refetchInterval: 30_000,
    retry: false,
  });
  const ok = health.isSuccess;
  if (health.isPending) return null;
  return (
    <span
      role="status"
      className={cn(
        "items-center gap-1.5 text-xs text-muted-foreground",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "size-2 rounded-full",
          ok ? "bg-status-good" : "bg-status-critical",
        )}
      />
      {ok ? "Сервис подключён" : "Нет связи с сервером"}
    </span>
  );
}
