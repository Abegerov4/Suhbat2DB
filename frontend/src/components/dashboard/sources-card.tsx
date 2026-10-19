"use client";

import { Database, ThumbsDown, ThumbsUp } from "lucide-react";
import Link from "next/link";

import { DatasourceStatusBadge } from "@/components/datasources/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import type { Stats } from "@/lib/api/types";
import { formatNumber, plural } from "@/lib/format";
import { useDatasources } from "@/lib/queries";

export function SourcesCard({ stats }: { stats: Stats }) {
  const datasources = useDatasources();
  const rated = stats.feedback_up + stats.feedback_down;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Источники и оценки</CardTitle>
        <CardDescription>
          {stats.datasources_ready} из {stats.datasources}{" "}
          {plural(stats.datasources, ["источника", "источников", "источников"])}{" "}
          готовы к вопросам
        </CardDescription>
        <CardAction>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/datasources">Все</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {datasources.isPending ? (
          <Skeleton className="h-16" />
        ) : (
          <ul className="flex flex-col gap-3">
            {datasources.data?.slice(0, 4).map((d) => (
              <li key={d.id} className="flex items-center gap-3">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
                  <Database
                    className="size-4 text-muted-foreground"
                    aria-hidden
                  />
                </span>
                <Link
                  href={`/datasources/${d.id}`}
                  className="min-w-0 flex-1 hover:underline"
                >
                  <span className="block truncate text-sm font-medium">
                    {d.name}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {d.tables_count ?? "—"}{" "}
                    {plural(d.tables_count ?? 0, [
                      "таблица",
                      "таблицы",
                      "таблиц",
                    ])}
                  </span>
                </Link>
                <DatasourceStatusBadge status={d.status} />
              </li>
            ))}
          </ul>
        )}
        <Separator />
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">Оценки ответов</p>
          <div className="flex items-center gap-4 text-sm">
            <span className="inline-flex items-center gap-1.5">
              <ThumbsUp className="size-4 text-status-good" aria-hidden />
              <span className="sr-only">Полезных:</span>
              {formatNumber(stats.feedback_up)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <ThumbsDown className="size-4 text-status-critical" aria-hidden />
              <span className="sr-only">Неполезных:</span>
              {formatNumber(stats.feedback_down)}
            </span>
            <span className="text-xs text-muted-foreground">
              {rated
                ? `${Math.round((stats.feedback_up / rated) * 100)}% полезных`
                : "оценок пока нет"}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
