"use client";

import {
  Ban,
  ChartColumn,
  Code,
  Database,
  MessageCircleQuestion,
  Search,
  ShieldCheck,
  Sparkles,
  SplitSquareHorizontal,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useReducedMotion } from "motion/react";

import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtSearchResult,
  ChainOfThoughtSearchResults,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { BorderBeam } from "@/components/ui/border-beam";
import type { NodeName } from "@/lib/api/types";
import { plural } from "@/lib/format";
import { STEP_LABELS, type StepState } from "@/lib/turn";

const NODE_ICONS: Record<NodeName, LucideIcon> = {
  guard_input: ShieldCheck,
  schema_linking: Search,
  detect_ambiguity: SplitSquareHorizontal,
  clarify: MessageCircleQuestion,
  generate_sql: Code,
  validate_sql: ShieldCheck,
  self_correct: Wrench,
  execute: Database,
  explain_and_visualize: ChartColumn,
  refuse: Ban,
};

const TABLES_PREFIX = "Таблицы: ";

/** Текущий шаг агента в ленте чата: мерцающая подпись и луч по рамке. */
export function AgentThinking({ steps }: { steps: StepState[] }) {
  const reduced = useReducedMotion();
  const current = steps.at(-1);
  const label = current
    ? `${STEP_LABELS[current.node]}…`
    : "Агент начинает работу…";
  return (
    <p
      role="status"
      className="relative inline-flex w-fit items-center gap-2 overflow-hidden rounded-full border bg-card px-3 py-1.5 text-sm"
    >
      <Sparkles className="size-3.5 shrink-0 text-chart-1" aria-hidden />
      {reduced ? (
        <span className="text-muted-foreground">{label}</span>
      ) : (
        <Shimmer as="span" duration={1.6}>
          {label}
        </Shimmer>
      )}
      {!reduced && (
        <BorderBeam
          size={40}
          duration={3}
          colorFrom="var(--chart-1)"
          colorTo="var(--chart-7)"
        />
      )}
    </p>
  );
}

/**
 * Полный ход работы агента (панель анализа): шаги графа с иконками,
 * найденные таблицы — бейджами, причины решений — подписями.
 */
export function AgentTrace({
  steps,
  defaultOpen,
}: {
  steps: StepState[];
  defaultOpen: boolean;
}) {
  if (steps.length === 0) return null;
  return (
    <ChainOfThought defaultOpen={defaultOpen}>
      <ChainOfThoughtHeader>
        Ход работы агента · {steps.length}{" "}
        {plural(steps.length, ["шаг", "шага", "шагов"])}
      </ChainOfThoughtHeader>
      <ChainOfThoughtContent>
        {steps.map((step, i) => {
          const tables = step.detail?.startsWith(TABLES_PREFIX)
            ? step.detail.slice(TABLES_PREFIX.length).split(", ")
            : null;
          return (
            <ChainOfThoughtStep
              key={`${step.node}-${i}`}
              icon={NODE_ICONS[step.node]}
              label={STEP_LABELS[step.node]}
              status={step.status === "running" ? "active" : "complete"}
              description={tables ? undefined : step.detail}
            >
              {tables && (
                <ChainOfThoughtSearchResults>
                  {tables.map((t) => (
                    <ChainOfThoughtSearchResult key={t} className="font-mono">
                      {t}
                    </ChainOfThoughtSearchResult>
                  ))}
                </ChainOfThoughtSearchResults>
              )}
            </ChainOfThoughtStep>
          );
        })}
      </ChainOfThoughtContent>
    </ChainOfThought>
  );
}
