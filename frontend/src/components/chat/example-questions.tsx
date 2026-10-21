import {
  ChartColumn,
  ChartLine,
  CircleHelp,
  CreditCard,
  ShieldAlert,
  UserRoundSearch,
} from "lucide-react";

import { AnimatedLogo } from "@/components/layout/animated-logo";
import { Ripple } from "@/components/ui/ripple";
import { type Tone, ToneIcon } from "@/components/ui/tone-icon";

/** Примеры для демо-БД: однозначные, с уточнением и с отказом. */
export const EXAMPLES = [
  "Топ-5 регионов по выручке за 2025 год",
  "Динамика выручки по месяцам в 2026 году",
  "Покажи продажи за прошлый квартал",
  "Какой способ оплаты самый популярный?",
  "Кто лучший менеджер?",
  "Удали все отменённые заказы",
];

/** Иконка и цвет для каждого примера: что покажет агент (график, уточнение, отказ). */
const EXAMPLE_ICONS: Record<string, { icon: typeof ChartColumn; tone: Tone }> =
  {
    [EXAMPLES[0]]: { icon: ChartColumn, tone: 1 },
    [EXAMPLES[1]]: { icon: ChartLine, tone: 3 },
    [EXAMPLES[2]]: { icon: CircleHelp, tone: 4 },
    [EXAMPLES[3]]: { icon: CreditCard, tone: 7 },
    [EXAMPLES[4]]: { icon: UserRoundSearch, tone: 2 },
    [EXAMPLES[5]]: { icon: ShieldAlert, tone: 8 },
  };

export function ExampleQuestions({
  onPick,
  disabled,
}: {
  onPick: (question: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-8 py-10 text-center">
      <div className="flex flex-col items-center gap-3">
        <div className="relative flex size-40 items-center justify-center">
          <Ripple mainCircleSize={90} numCircles={4} mainCircleOpacity={0.2} />
          <AnimatedLogo className="size-16" />
        </div>
        <h2 className="bg-gradient-to-b from-foreground to-foreground/50 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          О чём спросить данные?
        </h2>
        <p className="max-w-md text-sm text-balance text-muted-foreground">
          Пишите как коллеге-аналитику. Если вопрос неоднозначен, агент уточнит,
          а каждый SQL пройдёт пять уровней проверки до выполнения.
        </p>
      </div>
      <div className="grid w-full gap-2 sm:grid-cols-2">
        {EXAMPLES.map((q) => {
          const { icon, tone } = EXAMPLE_ICONS[q];
          return (
            <button
              key={q}
              type="button"
              disabled={disabled}
              onClick={() => onPick(q)}
              className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5 text-left text-sm transition-colors outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
            >
              <ToneIcon icon={icon} tone={tone} className="size-8" />
              {q}
            </button>
          );
        })}
      </div>
    </div>
  );
}
