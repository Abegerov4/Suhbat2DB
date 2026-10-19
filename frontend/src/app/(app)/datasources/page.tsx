"use client";

import {
  Database,
  MoreHorizontal,
  RefreshCw,
  TableProperties,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { ConnectDialog } from "@/components/datasources/connect-dialog";
import { DatasourceStatusBadge } from "@/components/datasources/status-badge";
import { SiteHeader } from "@/components/layout/site-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import type { Datasource } from "@/lib/api/types";
import { formatDateTime, plural } from "@/lib/format";
import {
  useDatasources,
  useDeleteDatasource,
  useMe,
  useReindex,
} from "@/lib/queries";

export default function DatasourcesPage() {
  const me = useMe();
  const datasources = useDatasources();
  const isAdmin = me.data?.role === "admin";

  return (
    <>
      <SiteHeader
        title="Источники данных"
        description="Базы PostgreSQL, к которым агент задаёт вопросы"
      >
        {isAdmin && <ConnectDialog />}
      </SiteHeader>
      <div className="flex flex-1 flex-col gap-4 p-4 sm:p-6">
        {datasources.isError && (
          <Alert variant="destructive">
            <AlertDescription>{datasources.error.message}</AlertDescription>
          </Alert>
        )}
        {datasources.isPending ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-40 rounded-xl" />
            ))}
          </div>
        ) : datasources.data?.length === 0 ? (
          <Empty className="border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Database aria-hidden />
              </EmptyMedia>
              <EmptyTitle>Источников пока нет</EmptyTitle>
              <EmptyDescription>
                {isAdmin
                  ? "Подключите базу с ролью только для чтения."
                  : "Попросите администратора подключить базу данных."}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {datasources.data?.map((d) => (
              <DatasourceCard key={d.id} datasource={d} isAdmin={isAdmin} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function DatasourceCard({
  datasource: d,
  isAdmin,
}: {
  datasource: Datasource;
  isAdmin: boolean;
}) {
  const reindex = useReindex();
  const remove = useDeleteDatasource();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="size-4 text-muted-foreground" aria-hidden />
          <span className="truncate">{d.name}</span>
        </CardTitle>
        <CardDescription>
          PostgreSQL · {d.tables_count ?? "—"}{" "}
          {plural(d.tables_count ?? 0, ["таблица", "таблицы", "таблиц"])}
        </CardDescription>
        {isAdmin && (
          <CardAction>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Действия с «${d.name}»`}
                >
                  <MoreHorizontal aria-hidden />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  disabled={d.status === "indexing"}
                  onSelect={() =>
                    reindex.mutate(d.id, {
                      onSuccess: () => toast.success("Переиндексация запущена"),
                      onError: (e) => toast.error(e.message),
                    })
                  }
                >
                  <RefreshCw aria-hidden />
                  Переиндексировать
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onSelect={() => {
                    if (
                      window.confirm(
                        `Удалить «${d.name}»? Диалоги с этим источником тоже будут удалены.`,
                      )
                    ) {
                      remove.mutate(d.id, {
                        onSuccess: () => toast.success("Источник удалён"),
                        onError: (e) => toast.error(e.message),
                      });
                    }
                  }}
                >
                  <Trash2 aria-hidden />
                  Удалить
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <DatasourceStatusBadge status={d.status} />
          {d.indexed_at && (
            <span className="text-xs text-muted-foreground">
              индекс: {formatDateTime(d.indexed_at)}
            </span>
          )}
        </div>
        {d.status === "error" && d.error && (
          <p className="line-clamp-3 text-xs break-words text-status-critical">
            {d.error}
          </p>
        )}
        <Button
          variant="outline"
          size="sm"
          asChild
          disabled={d.status !== "ready"}
        >
          <Link href={`/datasources/${d.id}`}>
            <TableProperties aria-hidden />
            Схема
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
