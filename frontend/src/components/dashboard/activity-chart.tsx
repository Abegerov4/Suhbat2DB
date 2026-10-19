"use client";

import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import type { DailyActivity } from "@/lib/api/types";
import { formatDay } from "@/lib/format";

const config = {
  questions: { label: "Вопросы", color: "var(--chart-2)" },
  answered: { label: "Ответы с данными", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function ActivityChart({ activity }: { activity?: DailyActivity[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Активность</CardTitle>
        <CardDescription>
          Вопросы к агенту и ответы с результатом запроса за последние{" "}
          {activity?.length ?? 14} дней
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!activity ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <ChartContainer config={config} className="aspect-auto h-64 w-full">
            <AreaChart
              data={activity.map((d) => ({ ...d, label: formatDay(d.date) }))}
              margin={{ left: 4, right: 8, top: 8 }}
              accessibilityLayer
            >
              <defs>
                <linearGradient id="fillAnswered" x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor="var(--color-answered)"
                    stopOpacity={0.25}
                  />
                  <stop
                    offset="100%"
                    stopColor="var(--color-answered)"
                    stopOpacity={0.02}
                  />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                minTickGap={24}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={32}
                allowDecimals={false}
              />
              <ChartTooltip
                cursor
                content={<ChartTooltipContent indicator="line" />}
              />
              <ChartLegend itemSorter={null} content={<ChartLegendContent />} />
              {/* серии различаются и формой (линия / заливка), не только цветом */}
              <Area
                isAnimationActive={false}
                dataKey="questions"
                type="linear"
                stroke="var(--color-questions)"
                fill="none"
                strokeWidth={2}
              />
              <Area
                isAnimationActive={false}
                dataKey="answered"
                type="linear"
                stroke="var(--color-answered)"
                fill="url(#fillAnswered)"
                strokeWidth={2}
              />
            </AreaChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
