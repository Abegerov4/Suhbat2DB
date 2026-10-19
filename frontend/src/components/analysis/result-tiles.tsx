import type { QueryResult } from "@/lib/api/types";
import { formatCell, isNumericType } from "@/lib/format";

/** Результат из одной строки — крупные числа вместо графика из одного столбца. */
export const isSingleRow = (result?: QueryResult) =>
  result?.row_count === 1 && result.columns.length <= 4;

export function ResultTiles({ result }: { result: QueryResult }) {
  const row = result.rows[0];
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {result.columns.map((c, i) => (
        <div key={c.name + i} className="rounded-xl border bg-card p-4">
          <dt className="truncate text-xs text-muted-foreground">{c.name}</dt>
          <dd
            className={
              isNumericType(c.type)
                ? "mt-1 text-3xl font-semibold tracking-tight"
                : "mt-1 text-lg font-medium break-words"
            }
          >
            {formatCell(row[i], c.type)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
