import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { LEVEL_LABELS } from "@/components/analysis/validation-report";
import type { LevelName, Stats } from "@/lib/api/types";
import { formatDuration, formatNumber, percent } from "@/lib/format";

/** Где валидатор останавливал SQL: защита в глубину, уровень за уровнем. */
export function ValidationSummary({ stats }: { stats: Stats }) {
  const total = stats.queries_ok + stats.queries_blocked + stats.queries_failed;
  const maxBlocked = Math.max(1, ...stats.blocked_by_level.map((b) => b.count));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Проверка SQL</CardTitle>
        <CardDescription>
          На каком уровне валидатор остановил запрос
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <dl className="grid grid-cols-3 gap-2 text-center">
          <Metric label="выполнено" value={stats.queries_ok} total={total} />
          <Metric
            label="заблокировано"
            value={stats.queries_blocked}
            total={total}
          />
          <Metric
            label="ошибка БД"
            value={stats.queries_failed}
            total={total}
          />
        </dl>
        <ul className="flex flex-col gap-3">
          {stats.blocked_by_level.map((b) => (
            <li key={b.level} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">
                  <span className="text-muted-foreground">{b.level}.</span>{" "}
                  {LEVEL_LABELS[b.name as LevelName] ?? b.name}
                </span>
                <span className="tabular shrink-0 text-xs text-muted-foreground">
                  {formatNumber(b.count)}
                </span>
              </div>
              <Progress
                value={(b.count / maxBlocked) * 100}
                aria-label={`Остановлено на уровне ${b.level}: ${b.count}`}
                className="h-1.5"
              />
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground">
          {stats.avg_duration_ms !== null
            ? `Среднее время выполнения запроса — ${formatDuration(stats.avg_duration_ms)}`
            : "Запросов к базе ещё не было"}
        </p>
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  total,
}: {
  label: string;
  value: number;
  total: number;
}) {
  return (
    <div className="rounded-lg border px-2 py-2">
      <dd className="text-lg font-semibold">{formatNumber(value)}</dd>
      <dt className="text-xs text-muted-foreground">
        {label}
        {total > 0 && ` · ${percent(value, total)}%`}
      </dt>
    </div>
  );
}
