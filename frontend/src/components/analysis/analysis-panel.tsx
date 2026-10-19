"use client";

import { BarChart3, Code2, ShieldCheck, Table2, Wrench } from "lucide-react";
import { useState } from "react";

import { AgentProgress } from "@/components/chat/agent-progress";
import { Badge } from "@/components/ui/badge";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { countOf, formatDuration, ROWS } from "@/lib/format";
import { lastAttempt, type Turn } from "@/lib/turn";

import { ChartView } from "./chart-view";
import { ResultTable } from "./result-table";
import { isSingleRow, ResultTiles } from "./result-tiles";
import { SqlPanel } from "./sql-panel";
import { ValidationReport } from "./validation-report";

type Tab = "chart" | "table" | "sql" | "validation";

const hasPlot = (turn: Turn) =>
  Boolean(turn.result && turn.chart && turn.chart.type !== "none");

function defaultTab(turn: Turn): Tab {
  if (hasPlot(turn) || isSingleRow(turn.result)) return "chart";
  if (turn.result) return "table";
  if (turn.attempts.length) return "validation";
  return "sql";
}

/**
 * Аналитическая панель: подробности выбранного ответа — график, таблица,
 * SQL с историей самокоррекции и отчёт пяти уровней проверки.
 */
export function AnalysisPanel({
  turn,
  question,
}: {
  turn: Turn | null;
  question?: string;
}) {
  if (!turn) {
    return (
      <Empty className="h-full">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <BarChart3 aria-hidden />
          </EmptyMedia>
          <EmptyTitle>Панель анализа</EmptyTitle>
          <EmptyDescription>
            Здесь появятся график, таблица результата, SQL и отчёт его проверки.
            Задайте вопрос или выберите ответ в чате.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  // key: при выборе другого ответа вкладка выбирается заново
  return <PanelBody key={turn.key} turn={turn} question={question} />;
}

function PanelBody({ turn, question }: { turn: Turn; question?: string }) {
  const [tab, setTab] = useState<Tab | null>(null);
  const active = tab ?? defaultTab(turn);
  const attempt = lastAttempt(turn);
  const streaming = turn.phase === "streaming";
  const hasChart = hasPlot(turn);
  const single = !hasChart && isSingleRow(turn.result);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-col gap-2 border-b px-4 py-3 sm:px-6">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Анализ ответа
        </p>
        {question && (
          <h2 className="line-clamp-2 text-base font-semibold">{question}</h2>
        )}
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {turn.result && (
            <>
              <span>{countOf(turn.result.row_count, ROWS)}</span>
              <span aria-hidden>·</span>
              <span>{formatDuration(turn.result.duration_ms)}</span>
            </>
          )}
          {turn.attempts.length > 1 && (
            <Badge variant="secondary" className="gap-1">
              <Wrench className="size-3" aria-hidden />
              самокоррекция: {turn.attempts.length} попытки
            </Badge>
          )}
        </div>
      </div>

      {streaming && !turn.result && (
        <div className="border-b px-4 py-4 sm:px-6">
          <AgentProgress steps={turn.steps} />
        </div>
      )}

      <Tabs
        value={active}
        onValueChange={(v) => setTab(v as Tab)}
        className="flex min-h-0 flex-1 flex-col gap-0"
      >
        <div className="overflow-x-auto px-4 pt-3 sm:px-6">
          <TabsList>
            <TabsTrigger value="chart" disabled={!hasChart && !single}>
              <BarChart3 aria-hidden />
              {single ? "Итог" : "График"}
            </TabsTrigger>
            <TabsTrigger value="table" disabled={!turn.result}>
              <Table2 aria-hidden />
              Таблица
            </TabsTrigger>
            <TabsTrigger value="sql" disabled={!attempt}>
              <Code2 aria-hidden />
              SQL
            </TabsTrigger>
            <TabsTrigger value="validation" disabled={!attempt}>
              <ShieldCheck aria-hidden />
              Проверка
            </TabsTrigger>
          </TabsList>
        </div>
        <ScrollArea className="min-h-0 flex-1">
          <div className="px-4 py-4 sm:px-6">
            <TabsContent value="chart">
              {hasChart && (
                <figure className="flex flex-col gap-2">
                  {turn.chart!.title && (
                    <figcaption className="text-sm font-medium">
                      {turn.chart!.title}
                    </figcaption>
                  )}
                  <ChartView result={turn.result!} spec={turn.chart!} />
                </figure>
              )}
              {single && <ResultTiles result={turn.result!} />}
            </TabsContent>
            <TabsContent value="table">
              {turn.result && (
                <ResultTable result={turn.result} filename="suhbat2db" />
              )}
            </TabsContent>
            <TabsContent value="sql">
              <SqlPanel attempts={turn.attempts} />
            </TabsContent>
            <TabsContent value="validation">
              {attempt && (
                <ValidationReport levels={attempt.levels} pending={streaming} />
              )}
            </TabsContent>
          </div>
        </ScrollArea>
      </Tabs>
    </div>
  );
}
