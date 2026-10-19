"use client";

import { ArrowUpRight, MessageSquare } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/format";
import { useDatasources, useSessions } from "@/lib/queries";

export function RecentSessions() {
  const sessions = useSessions();
  const datasources = useDatasources();
  const names = new Map(datasources.data?.map((d) => [d.id, d.name]));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Последние диалоги</CardTitle>
        <CardDescription>
          Продолжите анализ с того места, где остановились
        </CardDescription>
        <CardAction>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/chat">Новый</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {sessions.isPending ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : sessions.data?.length ? (
          <ol className="flex flex-col gap-1">
            {sessions.data.slice(0, 6).map((s) => (
              <li key={s.id}>
                <Link
                  href={`/chat/${s.id}`}
                  className="group flex items-start gap-3 rounded-md p-2 outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-muted">
                    <MessageSquare
                      className="size-3.5 text-muted-foreground"
                      aria-hidden
                    />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {s.title}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {names.get(s.datasource_id) ?? "Источник"} ·{" "}
                      {formatDateTime(s.created_at)}
                    </span>
                  </span>
                  <ArrowUpRight
                    className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                    aria-hidden
                  />
                </Link>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">
            Диалогов пока нет. Начните с вопроса к демо-базе.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
