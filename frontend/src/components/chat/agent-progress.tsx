import { CircleCheck } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import { STEP_LABELS, type StepState } from "@/lib/turn";

/** Живая лента шагов графа по событиям step. */
export function AgentProgress({
  steps,
  compact = false,
}: {
  steps: StepState[];
  compact?: boolean;
}) {
  if (steps.length === 0) {
    return (
      <p
        className="flex items-center gap-2 text-sm text-muted-foreground"
        role="status"
      >
        <Spinner /> Агент начинает работу…
      </p>
    );
  }
  const shown = compact ? steps.slice(-1) : steps;
  return (
    <ol
      className={cn("flex flex-col", compact ? "gap-1" : "gap-2.5")}
      role="status"
      aria-live="polite"
    >
      {shown.map((step, i) => (
        <li
          key={`${step.node}-${i}`}
          className="flex items-start gap-2 text-sm"
        >
          {step.status === "running" ? (
            <Spinner className="mt-0.5 size-4 shrink-0" />
          ) : (
            <CircleCheck
              className="mt-0.5 size-4 shrink-0 text-status-good"
              aria-hidden
            />
          )}
          <span className="min-w-0">
            <span
              className={cn(
                step.status === "running"
                  ? "font-medium"
                  : "text-muted-foreground",
              )}
            >
              {STEP_LABELS[step.node]}
              {step.status === "running" && "…"}
            </span>
            {step.detail && !compact && (
              <span className="block text-xs text-muted-foreground">
                {step.detail}
              </span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}
