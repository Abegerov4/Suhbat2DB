import {
  Ban,
  CircleStop,
  RotateCw,
  ShieldAlert,
  TriangleAlert,
  WifiOff,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { AgentError } from "@/lib/api/types";

const KIND: Record<string, { title: string; icon: typeof Ban }> = {
  refused: { title: "Запрос отклонён", icon: Ban },
  unsafe_input: { title: "Небезопасный запрос", icon: ShieldAlert },
  unsafe_sql: { title: "SQL заблокирован проверкой", icon: ShieldAlert },
  out_of_scope: { title: "Вопрос не о данных", icon: Ban },
  max_attempts: {
    title: "Не удалось составить корректный SQL",
    icon: TriangleAlert,
  },
  cannot_answer: { title: "В данных нет ответа", icon: TriangleAlert },
  no_connection: { title: "База данных недоступна", icon: WifiOff },
  connection_lost: { title: "Соединение прервалось", icon: WifiOff },
  cancelled: { title: "Ответ остановлен", icon: CircleStop },
};

/** Отказ или ошибка — отдельная карточка с понятным текстом, а не всплывающее уведомление. */
export function ErrorCard({
  error,
  onRetry,
}: {
  error: AgentError;
  onRetry?: () => void;
}) {
  const kind = KIND[error.code] ?? {
    title: "Ошибка агента",
    icon: TriangleAlert,
  };
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-status-critical/40 bg-status-critical/5 p-4"
    >
      <kind.icon
        className="mt-0.5 size-4 shrink-0 text-status-critical"
        aria-hidden
      />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-sm font-medium">{kind.title}</p>
        <p className="text-sm text-muted-foreground">{error.message}</p>
        {onRetry && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="mt-2 self-start"
          >
            <RotateCw aria-hidden />
            Повторить
          </Button>
        )}
      </div>
    </div>
  );
}
