import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/** Номер цвета категориальной палитры графиков (--chart-1 … --chart-8). */
export type Tone = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;

/**
 * Иконка в цветной плашке: общий элемент страницы входа (орбиты) и приложения
 * (карточки обзора, примеры вопросов). Цвет берётся из палитры графиков.
 */
export function ToneIcon({
  icon: Icon,
  tone,
  className,
}: {
  icon: LucideIcon;
  tone: Tone;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      style={{
        color: `var(--chart-${tone})`,
        background: `color-mix(in oklab, var(--chart-${tone}) 16%, var(--card))`,
        borderColor: `color-mix(in oklab, var(--chart-${tone}) 35%, transparent)`,
      }}
      className={cn(
        "flex shrink-0 items-center justify-center rounded-lg border",
        className,
      )}
    >
      <Icon className="size-1/2" strokeWidth={1.75} />
    </span>
  );
}
