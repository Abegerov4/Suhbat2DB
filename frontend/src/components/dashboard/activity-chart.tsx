"use client";

import {
  CircleCheck,
  type LucideIcon,
  MessageCircleQuestion,
  MessagesSquare,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { type Tone, ToneIcon } from "@/components/ui/tone-icon";
import type { DailyActivity } from "@/lib/api/types";
import { formatDay, formatNumber } from "@/lib/format";
import { useStats } from "@/lib/queries";
import { cn } from "@/lib/utils";

type Metric = "questions" | "answered" | "clarifications" | "refused";

/** Цвета совпадают с карточками обзора: вопросы, ответы, уточнения, отказы. */
const METRICS: {
  key: Metric;
  label: string;
  icon: LucideIcon;
  tone: Tone;
}[] = [
  { key: "questions", label: "Вопросы", icon: MessagesSquare, tone: 1 },
  { key: "answered", label: "Ответы с данными", icon: CircleCheck, tone: 3 },
  {
    key: "clarifications",
    label: "Уточнения",
    icon: MessageCircleQuestion,
    tone: 4,
  },
  { key: "refused", label: "Отказы", icon: ShieldAlert, tone: 8 },
];

const config = Object.fromEntries(
  METRICS.map((m) => [
    m.key,
    { label: m.label, color: `var(--chart-${m.tone})` },
  ]),
) satisfies ChartConfig;

const PERIODS = [7, 14, 30] as const;
type Period = (typeof PERIODS)[number];

const sum = (days: DailyActivity[], key: Metric) =>
  days.reduce((total, d) => total + d[key], 0);

/** Изменение к предыдущему периоду той же длины; null, если сравнивать не с чем. */
function change(current: number, previous: number): number | null {
  if (previous === 0) return null;
  return Math.round(((current - previous) / previous) * 100);
}

function ActivityTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { dataKey?: string | number; value?: number }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-48 rounded-lg border bg-popover/95 p-3 shadow-lg backdrop-blur-sm">
      <p className="mb-2 border-b pb-2 text-sm font-semibold">{label}</p>
      <div className="space-y-1.5">
        {METRICS.map((m) => {
          const value = payload.find((p) => p.dataKey === m.key)?.value ?? 0;
          return (
            <div
              key={m.key}
              className="flex items-center justify-between gap-3"
            >
              <span className="flex items-center gap-2 text-xs text-muted-foreground">
                <span
                  className="size-2.5 rounded-sm"
                  style={{ background: `var(--color-${m.key})` }}
                />
                {m.label}
              </span>
              <span className="text-sm font-semibold tabular-nums">
                {formatNumber(value)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Активность за период: сводка по четырём исходам хода агента и график по дням. */
export function ActivityChart() {
  const [period, setPeriod] = useState<Period>(14);
  // вдвое больше дней: вторая половина — текущий период, первая — для сравнения
  const stats = useStats(period * 2);
  const days = stats.data?.activity;
  const current = days?.slice(period);
  const previous = days?.slice(0, period);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Активность</CardTitle>
        <CardDescription>
          Вопросы к агенту и исходы ответов по дням
        </CardDescription>
        <CardAction>
          <Select
            value={String(period)}
            onValueChange={(v) => setPeriod(Number(v) as Period)}
          >
            <SelectTrigger size="sm" aria-label="Период">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              {PERIODS.map((p) => (
                <SelectItem key={p} value={String(p)}>
                  Последние {p} дней
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-8">
        {!current || !previous ? (
          <>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-72 w-full" />
          </>
        ) : (
          <>
            <dl className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
              {METRICS.map((m) => {
                const value = sum(current, m.key);
                const delta = change(value, sum(previous, m.key));
                return (
                  <div
                    key={m.key}
                    className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1"
                  >
                    <dt className="col-start-2 text-sm text-muted-foreground">
                      {m.label}
                    </dt>
                    <dd className="col-start-1 row-span-2 row-start-1">
                      <ToneIcon
                        icon={m.icon}
                        tone={m.tone}
                        className="size-10"
                      />
                    </dd>
                    <dd className="col-start-2 flex items-baseline gap-2">
                      <span className="text-2xl leading-none font-semibold tabular-nums">
                        {formatNumber(value)}
                      </span>
                      {delta === null ? null : (
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 text-xs font-medium",
                            delta >= 0
                              ? "text-status-good"
                              : "text-status-critical",
                          )}
                        >
                          {delta >= 0 ? (
                            <TrendingUp className="size-3.5" aria-hidden />
                          ) : (
                            <TrendingDown className="size-3.5" aria-hidden />
                          )}
                          {delta >= 0 ? "+" : "−"}
                          {Math.abs(delta)}%
                          <span className="sr-only">
                            к предыдущим {period} дням
                          </span>
                        </span>
                      )}
                    </dd>
                  </div>
                );
              })}
            </dl>
            <p className="-mt-4 text-xs text-muted-foreground">
              Изменение показано относительно предыдущих {period} дней, если в
              них была активность.
            </p>

            <ChartContainer config={config} className="aspect-auto h-72 w-full">
              <AreaChart
                data={current.map((d) => ({ ...d, label: formatDay(d.date) }))}
                margin={{ left: 4, right: 8, top: 8 }}
                accessibilityLayer
              >
                <defs>
                  <pattern
                    id="activityPattern"
                    width="24"
                    height="24"
                    patternUnits="userSpaceOnUse"
                  >
                    <path
                      d="M0,12 L24,12 M12,0 L12,24"
                      stroke="var(--border)"
                      strokeWidth="0.6"
                    />
                    <circle cx="6" cy="6" r="1" fill="var(--border)" />
                  </pattern>
                  {METRICS.map((m) => (
                    <linearGradient
                      key={m.key}
                      id={`fill-${m.key}`}
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor={`var(--color-${m.key})`}
                        stopOpacity={0.35}
                      />
                      <stop
                        offset="95%"
                        stopColor={`var(--color-${m.key})`}
                        stopOpacity={0.02}
                      />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="label"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={10}
                  minTickGap={24}
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={32}
                  allowDecimals={false}
                />
                <ChartTooltip
                  cursor={{ strokeDasharray: "4 4", stroke: "var(--ring)" }}
                  content={<ActivityTooltip />}
                />
                {/* узор под самой большой серией — фон области графика */}
                <Area
                  dataKey="questions"
                  type="monotone"
                  fill="url(#activityPattern)"
                  stroke="transparent"
                  isAnimationActive={false}
                  activeDot={false}
                />
                {/* серии не складываются: ответы, уточнения и отказы — исходы вопросов */}
                {METRICS.map((m) => (
                  <Area
                    key={m.key}
                    dataKey={m.key}
                    type="monotone"
                    fill={`url(#fill-${m.key})`}
                    stroke={`var(--color-${m.key})`}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{
                      r: 4,
                      fill: `var(--color-${m.key})`,
                      stroke: "var(--background)",
                      strokeWidth: 1.5,
                    }}
                    isAnimationActive={false}
                  />
                ))}
              </AreaChart>
            </ChartContainer>
          </>
        )}
      </CardContent>
    </Card>
  );
}
