import { CircleCheck, CircleDashed, CircleX, Lightbulb } from "lucide-react";

import { cn } from "@/lib/utils";
import type { LevelName, ValidationLevelResult } from "@/lib/api/types";

export const LEVEL_LABELS: Record<LevelName, string> = {
  syntax: "Синтаксис",
  readonly_policy: "Только чтение",
  schema: "Схема",
  explain: "План (EXPLAIN)",
  execution: "Выполнение",
};

const LEVEL_HINTS: Record<LevelName, string> = {
  syntax: "SQL разбирается парсером PostgreSQL",
  readonly_policy:
    "Только SELECT: без изменений данных, системных каталогов и опасных функций",
  schema: "Таблицы и столбцы существуют, типы в условиях совместимы",
  explain: "Оценка стоимости и поиск декартовых произведений до запуска",
  execution: "READ ONLY транзакция, таймаут и лимит строк",
};

const ORDER: LevelName[] = [
  "syntax",
  "readonly_policy",
  "schema",
  "explain",
  "execution",
];

/**
 * Отчёт пяти уровней валидатора. Уровень, на котором запрос остановлен,
 * выделен; уровни после него не проверялись. Статус — иконка + подпись.
 */
export function ValidationReport({
  levels,
  pending = false,
}: {
  levels: ValidationLevelResult[];
  pending?: boolean;
}) {
  const byName = new Map(levels.map((l) => [l.name, l]));
  const failed = levels.find((l) => !l.passed);

  return (
    <ol className="flex flex-col gap-2" aria-label="Проверка SQL по уровням">
      {ORDER.map((name, i) => {
        const level = byName.get(name);
        const state = level
          ? level.passed
            ? "passed"
            : "failed"
          : failed || !pending
            ? "skipped"
            : "waiting";
        return (
          <li
            key={name}
            className={cn(
              "flex gap-3 rounded-lg border p-3",
              state === "failed" &&
                "border-status-critical/50 bg-status-critical/5",
              state === "skipped" && "opacity-60",
            )}
          >
            <StatusIcon state={state} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                <p className="text-sm font-medium">
                  <span className="text-muted-foreground">{i + 1}.</span>{" "}
                  {LEVEL_LABELS[name]}
                </p>
                <p className="text-xs text-muted-foreground">
                  {
                    {
                      passed: "пройден",
                      failed: level?.fatal ? "заблокирован" : "не пройден",
                      skipped: "не проверялся",
                      waiting: "ожидает",
                    }[state]
                  }
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                {level?.message ?? LEVEL_HINTS[name]}
              </p>
              {level?.hint && (
                <p className="mt-1.5 flex gap-1.5 text-xs">
                  <Lightbulb
                    className="mt-px size-3.5 shrink-0 text-status-warning"
                    aria-hidden
                  />
                  <span>{level.hint}</span>
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function StatusIcon({
  state,
}: {
  state: "passed" | "failed" | "skipped" | "waiting";
}) {
  const common = "mt-0.5 size-4 shrink-0";
  if (state === "passed")
    return (
      <CircleCheck className={cn(common, "text-status-good")} aria-hidden />
    );
  if (state === "failed")
    return (
      <CircleX className={cn(common, "text-status-critical")} aria-hidden />
    );
  return (
    <CircleDashed
      className={cn(
        common,
        "text-muted-foreground",
        state === "waiting" && "animate-pulse",
      )}
      aria-hidden
    />
  );
}

/** Компактная строка из пяти значков для карточки ответа в чате. */
export function ValidationBadges({
  levels,
}: {
  levels: ValidationLevelResult[];
}) {
  const byName = new Map(levels.map((l) => [l.name, l]));
  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label="Проверка SQL"
    >
      {ORDER.map((name) => {
        const level = byName.get(name);
        const label = `${LEVEL_LABELS[name]}: ${level ? (level.passed ? "пройден" : "не пройден") : "не проверялся"}`;
        return level?.passed ? (
          <CircleCheck
            key={name}
            className="size-3.5 text-status-good"
            role="img"
            aria-label={label}
          />
        ) : level ? (
          <CircleX
            key={name}
            className="size-3.5 text-status-critical"
            role="img"
            aria-label={label}
          />
        ) : (
          <CircleDashed
            key={name}
            className="size-3.5 text-muted-foreground"
            role="img"
            aria-label={label}
          />
        );
      })}
    </span>
  );
}
