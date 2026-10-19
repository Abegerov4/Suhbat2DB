"use client";

import { CircleHelp } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type {
  ClarificationAnswer,
  ClarificationRequest,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

const TYPE_LABEL = {
  metric: "показатель",
  temporal: "период",
  value: "значение",
  schema: "данные",
  scope: "охват",
} as const;

type Choice = { optionId?: string; freeText?: string };

/**
 * Human-in-the-loop: агент остановил граф и ждёт выбора по каждой
 * неоднозначности — вариант кнопкой или свой ответ текстом.
 */
export function ClarificationCard({
  request,
  active,
  onSubmit,
}: {
  request: ClarificationRequest;
  active: boolean;
  onSubmit: (answers: ClarificationAnswer[], summary: string) => void;
}) {
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const complete = request.ambiguities.every(
    (a) => choices[a.id]?.optionId || choices[a.id]?.freeText?.trim(),
  );

  function submit() {
    const answers = request.ambiguities.map((a) => {
      const c = choices[a.id];
      return c.optionId
        ? { ambiguity_id: a.id, option_id: c.optionId }
        : { ambiguity_id: a.id, free_text: c.freeText!.trim() };
    });
    const summary = request.ambiguities
      .map((a) => {
        const c = choices[a.id];
        const label =
          a.options.find((o) => o.id === c.optionId)?.label ?? c.freeText;
        return `${a.span} → ${label}`;
      })
      .join("; ");
    onSubmit(answers, summary);
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-chart-1/40 bg-chart-1/5 p-4">
      <p className="flex items-start gap-2 text-sm font-medium">
        <CircleHelp
          className="mt-0.5 size-4 shrink-0 text-chart-1"
          aria-hidden
        />
        {request.question}
      </p>
      {request.ambiguities.map((a) => {
        const choice = choices[a.id] ?? {};
        return (
          <fieldset
            key={a.id}
            className="flex flex-col gap-2"
            disabled={!active}
          >
            <legend className="mb-2 flex flex-wrap items-center gap-2 text-sm">
              «{a.span}»
              <Badge variant="outline" className="font-normal">
                {TYPE_LABEL[a.type]}
              </Badge>
            </legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {a.options.map((o) => {
                const selected = choice.optionId === o.id;
                return (
                  <button
                    key={o.id}
                    type="button"
                    aria-pressed={selected}
                    onClick={() =>
                      setChoices((c) => ({ ...c, [a.id]: { optionId: o.id } }))
                    }
                    className={cn(
                      "flex flex-col items-start gap-0.5 rounded-lg border bg-background px-3 py-2 text-left text-sm transition-colors outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-60",
                      selected && "border-primary ring-1 ring-primary",
                    )}
                  >
                    <span className="font-medium">{o.label}</span>
                    {o.description && (
                      <span className="text-xs text-muted-foreground">
                        {o.description}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <Input
              placeholder="Свой вариант…"
              aria-label={`Свой вариант для «${a.span}»`}
              maxLength={500}
              value={choice.freeText ?? ""}
              onChange={(e) =>
                setChoices((c) => ({
                  ...c,
                  [a.id]: { freeText: e.target.value },
                }))
              }
              className="bg-background"
            />
          </fieldset>
        );
      })}
      {active ? (
        <Button onClick={submit} disabled={!complete} className="self-start">
          Продолжить
        </Button>
      ) : (
        <p className="text-xs text-muted-foreground">Уточнение получено</p>
      )}
    </div>
  );
}
