"use client";

import {
  BarChart3,
  ChartLine,
  ChartPie,
  ChartScatter,
  PanelRight,
  Table2,
} from "lucide-react";

import { ValidationBadges } from "@/components/analysis/validation-report";
import type { ClarificationAnswer } from "@/lib/api/types";
import { countOf, ROWS } from "@/lib/format";
import { hasAnalysis, lastAttempt, type Turn } from "@/lib/turn";
import { cn } from "@/lib/utils";

import { AgentThinking } from "./agent-progress";
import { ClarificationCard } from "./clarification-card";
import { ErrorCard } from "./error-card";
import { FeedbackButtons } from "./feedback-buttons";

const CHART_ICON = {
  bar: BarChart3,
  line: ChartLine,
  pie: ChartPie,
  scatter: ChartScatter,
  none: Table2,
};

/** Ход ассистента в ленте чата: текст, уточнение или отказ и ссылка на панель анализа. */
export function AnswerCard({
  turn,
  selected,
  onSelect,
  onClarify,
  onRetry,
}: {
  turn: Turn;
  selected: boolean;
  onSelect?: () => void;
  onClarify: (answers: ClarificationAnswer[], summary: string) => void;
  onRetry?: () => void;
}) {
  const streaming = turn.phase === "streaming";
  const attempt = lastAttempt(turn);
  const Icon = CHART_ICON[turn.chart?.type ?? "none"];

  return (
    <div className="flex flex-col gap-3">
      {streaming && !turn.answer && !turn.clarification && !turn.error && (
        <AgentThinking steps={turn.steps} />
      )}

      {turn.answer && (
        // ответ модели — обычный текст: без Markdown, ссылок и картинок (ai_security §8)
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {turn.answer}
          {streaming && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-foreground/60 align-text-bottom" />
          )}
        </p>
      )}

      {turn.clarification && (
        <ClarificationCard
          request={turn.clarification}
          active={turn.awaitingClarification && !streaming}
          onSubmit={onClarify}
        />
      )}

      {turn.error && <ErrorCard error={turn.error} onRetry={onRetry} />}

      {hasAnalysis(turn) && onSelect && (
        <button
          type="button"
          onClick={onSelect}
          aria-pressed={selected}
          className={cn(
            "flex w-full max-w-sm items-center gap-3 rounded-lg border bg-card px-3 py-2 text-left text-sm shadow-xs transition-colors outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
            selected && "border-primary/60 ring-1 ring-primary/40",
          )}
        >
          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
            <Icon className="size-4 text-muted-foreground" aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">
              {turn.result
                ? countOf(turn.result.row_count, ROWS)
                : streaming
                  ? "Проверка SQL…"
                  : "SQL не выполнен"}
            </span>
            {attempt && <ValidationBadges levels={attempt.levels} />}
          </span>
          <PanelRight
            className="size-4 shrink-0 text-muted-foreground"
            aria-hidden
          />
          <span className="sr-only">Открыть в панели анализа</span>
        </button>
      )}

      {turn.phase === "done" && turn.id && !turn.clarification && (
        <FeedbackButtons messageId={turn.id} />
      )}
    </div>
  );
}
