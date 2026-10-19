import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Datasource } from "@/lib/api/types";

const STATUS = {
  ready: { label: "Готов", icon: CircleCheck, className: "text-status-good" },
  indexing: {
    label: "Индексация",
    icon: LoaderCircle,
    className: "animate-spin text-muted-foreground",
  },
  error: {
    label: "Ошибка",
    icon: CircleAlert,
    className: "text-status-critical",
  },
} as const;

/** Статус всегда с иконкой и подписью: цвет не единственный носитель смысла. */
export function DatasourceStatusBadge({
  status,
}: {
  status: Datasource["status"];
}) {
  const s = STATUS[status];
  return (
    <Badge variant="outline" className="shrink-0 gap-1">
      <s.icon className={`size-3 ${s.className}`} aria-hidden />
      {s.label}
    </Badge>
  );
}
