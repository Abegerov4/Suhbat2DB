import { Sparkles } from "lucide-react";

/** Примеры для демо-БД: однозначные, с уточнением и с отказом. */
export const EXAMPLES = [
  "Топ-5 регионов по выручке за 2025 год",
  "Динамика выручки по месяцам в 2026 году",
  "Покажи продажи за прошлый квартал",
  "Какой способ оплаты самый популярный?",
  "Кто лучший менеджер?",
  "Удали все отменённые заказы",
];

export function ExampleQuestions({
  onPick,
  disabled,
}: {
  onPick: (question: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-6 py-10 text-center">
      <div className="flex flex-col items-center gap-2">
        <span className="flex size-10 items-center justify-center rounded-xl bg-muted">
          <Sparkles className="size-5 text-muted-foreground" aria-hidden />
        </span>
        <h2 className="text-lg font-semibold">О чём спросить данные?</h2>
        <p className="max-w-md text-sm text-balance text-muted-foreground">
          Пишите как коллеге-аналитику. Если вопрос неоднозначен, агент уточнит,
          а каждый SQL пройдёт пять уровней проверки до выполнения.
        </p>
      </div>
      <div className="grid w-full gap-2 sm:grid-cols-2">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            type="button"
            disabled={disabled}
            onClick={() => onPick(q)}
            className="rounded-lg border bg-card px-3 py-2.5 text-left text-sm transition-colors outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
