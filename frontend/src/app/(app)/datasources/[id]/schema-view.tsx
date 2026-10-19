"use client";

import { ChevronRight, KeyRound, Link2, Search, Table2 } from "lucide-react";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

import { SiteHeader } from "@/components/layout/site-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { TableInfo } from "@/lib/api/types";
import { formatCompact, plural } from "@/lib/format";
import { useDatasources, useSchema } from "@/lib/queries";

/** Обозреватель схемы: то, что агент видит при поиске таблиц (schema linking). */
export function SchemaView() {
  const { id } = useParams<{ id: string }>();
  const datasources = useDatasources();
  const datasource = datasources.data?.find((d) => d.id === id);
  const schema = useSchema(id, datasource?.status === "ready");
  const [query, setQuery] = useState("");

  const tables = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = schema.data?.tables ?? [];
    if (!q) return all;
    return all.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.comment?.toLowerCase().includes(q) ||
        t.columns.some(
          (c) =>
            c.name.toLowerCase().includes(q) ||
            c.comment?.toLowerCase().includes(q),
        ),
    );
  }, [schema.data, query]);

  return (
    <>
      <SiteHeader
        title={datasource ? `Схема: ${datasource.name}` : "Схема"}
        description={
          schema.data
            ? `${schema.data.tables.length} ${plural(schema.data.tables.length, ["таблица", "таблицы", "таблиц"])}${schema.data.timezone ? ` · часовой пояс ${schema.data.timezone}` : ""}`
            : undefined
        }
      />
      <div className="flex flex-1 flex-col gap-4 p-4 sm:p-6">
        <div className="relative max-w-sm">
          <Search
            className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Таблица, столбец или описание"
            aria-label="Поиск по схеме"
            className="pl-8"
          />
        </div>
        {datasource && datasource.status !== "ready" && (
          <Alert>
            <AlertDescription>
              {datasource.status === "indexing"
                ? "Схема ещё индексируется…"
                : `Ошибка индексации: ${datasource.error}`}
            </AlertDescription>
          </Alert>
        )}
        {schema.isError && (
          <Alert variant="destructive">
            <AlertDescription>{schema.error.message}</AlertDescription>
          </Alert>
        )}
        {schema.isPending && datasource?.status === "ready" && (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-14 rounded-xl" />
            ))}
          </div>
        )}
        <div className="flex flex-col gap-3">
          {tables.map((t) => (
            <TableCard
              key={`${t.schema_name}.${t.name}`}
              table={t}
              open={Boolean(query.trim())}
            />
          ))}
        </div>
      </div>
    </>
  );
}

function TableCard({ table, open }: { table: TableInfo; open: boolean }) {
  return (
    <Collapsible defaultOpen={open} key={String(open)} asChild>
      <Card className="gap-0 py-0">
        <CollapsibleTrigger className="group flex w-full items-center gap-3 px-4 py-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <ChevronRight
            className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-90"
            aria-hidden
          />
          <Table2
            className="size-4 shrink-0 text-muted-foreground"
            aria-hidden
          />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-sm font-medium">
              {table.schema_name !== "public" && `${table.schema_name}.`}
              {table.name}
            </span>
            {table.comment && (
              <span className="block truncate text-xs text-muted-foreground">
                {table.comment}
              </span>
            )}
          </span>
          <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">
            {table.columns.length}{" "}
            {plural(table.columns.length, ["столбец", "столбца", "столбцов"])} ·
            ~{formatCompact(table.row_estimate)} строк
          </span>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="overflow-x-auto border-t">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Столбец</TableHead>
                  <TableHead>Тип</TableHead>
                  <TableHead>Описание</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {table.columns.map((c) => (
                  <TableRow key={c.name}>
                    <TableCell className="align-top">
                      <span className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
                        {c.name}
                        {c.is_pk && (
                          <Badge
                            variant="secondary"
                            className="gap-1 px-1.5 font-sans"
                          >
                            <KeyRound className="size-3" aria-hidden />
                            PK
                          </Badge>
                        )}
                        {c.fk && (
                          <Badge
                            variant="outline"
                            className="gap-1 px-1.5 font-sans"
                            title={c.fk}
                          >
                            <Link2 className="size-3" aria-hidden />
                            {c.fk.split(".").slice(-2).join(".")}
                          </Badge>
                        )}
                      </span>
                    </TableCell>
                    <TableCell className="align-top font-mono text-xs text-muted-foreground">
                      {c.data_type}
                      {c.nullable ? "" : " not null"}
                    </TableCell>
                    <TableCell className="max-w-md align-top text-xs whitespace-normal">
                      {c.comment ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                      {c.sample_values && c.sample_values.length > 0 && (
                        <span className="mt-1 flex flex-wrap gap-1">
                          {c.sample_values.slice(0, 12).map((v) => (
                            <Badge
                              key={v}
                              variant="secondary"
                              className="font-normal"
                            >
                              {v}
                            </Badge>
                          ))}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
