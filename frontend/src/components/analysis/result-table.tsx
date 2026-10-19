"use client";

import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { QueryResult } from "@/lib/api/types";
import { toCsv } from "@/lib/chart";
import {
  COLUMNS,
  countOf,
  ROWS,
  formatCell,
  formatDuration,
  formatNumber,
  isNumericType,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

type Sort = { column: number; dir: "asc" | "desc" } | null;

function compare(a: unknown, b: unknown, numeric: boolean): number {
  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;
  if (numeric) return Number(a) - Number(b);
  return String(a).localeCompare(String(b), "ru");
}

export function ResultTable({
  result,
  filename = "result",
}: {
  result: QueryResult;
  filename?: string;
}) {
  const [sort, setSort] = useState<Sort>(null);
  const [page, setPage] = useState(0);

  const rows = useMemo(() => {
    if (!sort) return result.rows;
    const numeric = isNumericType(result.columns[sort.column].type);
    const sorted = [...result.rows].sort((a, b) =>
      compare(a[sort.column], b[sort.column], numeric),
    );
    return sort.dir === "asc" ? sorted : sorted.reverse();
  }, [result, sort]);

  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const visible = rows.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE);

  function toggle(column: number) {
    setPage(0);
    setSort((s) =>
      s?.column !== column
        ? { column, dir: "desc" }
        : s.dir === "desc"
          ? { column, dir: "asc" }
          : null,
    );
  }

  function download() {
    const blob = new Blob([toCsv(result)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: `${filename}.csv`,
    });
    a.click();
    URL.revokeObjectURL(url);
  }

  if (result.row_count === 0) {
    return (
      <p className="text-sm text-muted-foreground">Запрос не вернул строк.</p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {countOf(result.row_count, ROWS)} ·{" "}
          {countOf(result.columns.length, COLUMNS)} ·{" "}
          {formatDuration(result.duration_ms)}
        </p>
        <Button variant="outline" size="sm" onClick={download}>
          <Download aria-hidden />
          CSV
        </Button>
      </div>
      {result.truncated && (
        <p className="flex items-start gap-2 rounded-lg border border-status-warning/40 bg-status-warning/10 px-3 py-2 text-xs">
          <TriangleAlert
            className="mt-px size-3.5 shrink-0 text-status-warning"
            aria-hidden
          />
          Показаны первые {formatNumber(result.row_count)} строк: сработал лимит
          выдачи. Уточните вопрос или добавьте агрегацию.
        </p>
      )}
      {/* таблица прокручивается внутри карточки, а не всей страницей */}
      <div className="max-h-[28rem] overflow-auto rounded-lg border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-background">
            <TableRow>
              {result.columns.map((c, i) => {
                const numeric = isNumericType(c.type);
                const active = sort?.column === i;
                const Icon = !active
                  ? ArrowUpDown
                  : sort.dir === "asc"
                    ? ArrowUp
                    : ArrowDown;
                return (
                  <TableHead
                    key={c.name + i}
                    className={cn(numeric && "text-right")}
                    aria-sort={
                      active
                        ? sort.dir === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                  >
                    <button
                      type="button"
                      onClick={() => toggle(i)}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-sm outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
                        numeric && "flex-row-reverse",
                      )}
                      title={c.type}
                    >
                      {c.name}
                      <Icon
                        className={cn(
                          "size-3",
                          !active && "text-muted-foreground/60",
                        )}
                        aria-hidden
                      />
                    </button>
                  </TableHead>
                );
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map((row, r) => (
              <TableRow key={current * PAGE_SIZE + r}>
                {row.map((value, i) => {
                  const type = result.columns[i].type;
                  return (
                    <TableCell
                      key={i}
                      className={cn(
                        "max-w-72 truncate",
                        isNumericType(type) && "tabular text-right",
                        value === null && "text-muted-foreground",
                      )}
                    >
                      {formatCell(value, type)}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
          <span>
            Страница {current + 1} из {pages}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => setPage(current - 1)}
            disabled={current === 0}
            aria-label="Предыдущая страница"
          >
            <ChevronLeft aria-hidden />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => setPage(current + 1)}
            disabled={current >= pages - 1}
            aria-label="Следующая страница"
          >
            <ChevronRight aria-hidden />
          </Button>
        </div>
      )}
    </div>
  );
}
