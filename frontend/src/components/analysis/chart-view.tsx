"use client";

import { useId, useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
} from "recharts";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { ChartSpec, QueryResult } from "@/lib/api/types";
import { pieData, SERIES_COLORS, toChartData } from "@/lib/chart";
import { formatCompact } from "@/lib/format";

const axis = { tickLine: false, axisLine: false, tickMargin: 8 } as const;

/** График по спецификации бэкенда; null — график не уместен (например, одно число). */
export function ChartView({
  result,
  spec,
  className = "aspect-auto h-80 w-full",
}: {
  result: QueryResult;
  spec: ChartSpec;
  className?: string;
}) {
  const data = useMemo(() => toChartData(result, spec), [result, spec]);
  const gradientId = `fill-${useId().replace(/:/g, "")}`;
  if (!data) return null;
  const multi = data.y.length > 1;
  const valueAxis = (
    <YAxis
      {...axis}
      width={72}
      tickFormatter={(v: number) => formatCompact(v)}
    />
  );

  if (spec.type === "pie") {
    const slices = pieData(data);
    const config: ChartConfig = Object.fromEntries(
      slices.map((s, i) => [
        s.name,
        { label: s.name, color: SERIES_COLORS[i % 8] },
      ]),
    );
    return (
      <ChartContainer config={config} className={className}>
        <PieChart accessibilityLayer>
          <ChartTooltip
            content={<ChartTooltipContent nameKey="name" hideLabel />}
          />
          <Pie
            isAnimationActive={false}
            data={slices}
            dataKey="value"
            nameKey="name"
            innerRadius="45%"
            strokeWidth={2}
            stroke="var(--card)" // 2px зазор между секторами цвета поверхности
          >
            {slices.map((s) => (
              <Cell key={s.name} fill={s.fill} />
            ))}
          </Pie>
          <ChartLegend
            itemSorter={null} // порядок легенды = порядок секторов и цветов
            content={<ChartLegendContent nameKey="name" />}
            className="flex-wrap gap-2"
          />
        </PieChart>
      </ChartContainer>
    );
  }

  if (spec.type === "line") {
    // одна серия — площадь с градиентом; несколько — линии без заливки, чтобы не перекрывались
    return (
      <ChartContainer config={data.config} className={className}>
        <AreaChart
          data={data.rows}
          margin={{ left: 4, right: 12, top: 8 }}
          accessibilityLayer
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor="var(--color-s0)"
                stopOpacity={0.25}
              />
              <stop
                offset="100%"
                stopColor="var(--color-s0)"
                stopOpacity={0.02}
              />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="x" {...axis} minTickGap={24} />
          {valueAxis}
          <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
          {multi && (
            <ChartLegend itemSorter={null} content={<ChartLegendContent />} />
          )}
          {data.y.map((key) => (
            <Area
              isAnimationActive={false}
              key={key}
              dataKey={key}
              type="monotone"
              stroke={`var(--color-${key})`}
              fill={multi ? "none" : `url(#${gradientId})`}
              strokeWidth={2}
              dot={
                data.rows.length <= 24 ? { r: 3, fill: "var(--card)" } : false
              }
              activeDot={{ r: 5 }}
              connectNulls
            />
          ))}
        </AreaChart>
      </ChartContainer>
    );
  }

  if (spec.type === "scatter") {
    const key = data.y[0];
    return (
      <ChartContainer config={data.config} className={className}>
        <ScatterChart
          margin={{ left: 4, right: 12, top: 8 }}
          accessibilityLayer
        >
          <CartesianGrid />
          <XAxis
            dataKey="x"
            type="number"
            name={spec.x}
            {...axis}
            tickFormatter={(v: number) => formatCompact(v)}
          />
          <YAxis
            dataKey={key}
            type="number"
            name={String(data.config[key].label)}
            {...axis}
            width={72}
            tickFormatter={(v: number) => formatCompact(v)}
          />
          <ChartTooltip content={<ChartTooltipContent hideLabel />} />
          <Scatter
            isAnimationActive={false}
            data={data.rows}
            fill={`var(--color-${key})`}
          />
        </ScatterChart>
      </ChartContainer>
    );
  }

  // bar: длинные подписи категорий — горизонтальные столбцы
  const horizontal =
    data.rows.length > 6 || data.rows.some((r) => String(r.x).length > 14);
  return (
    <ChartContainer
      config={data.config}
      className={horizontal ? "aspect-auto w-full" : className}
      style={
        horizontal
          ? { height: Math.max(240, data.rows.length * 28 + 48) }
          : undefined
      }
    >
      <BarChart
        data={data.rows}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ left: 4, right: 12, top: 8 }}
        barCategoryGap={horizontal ? 4 : "20%"}
        accessibilityLayer
      >
        <CartesianGrid vertical={horizontal} horizontal={!horizontal} />
        {horizontal ? (
          <>
            <XAxis
              type="number"
              {...axis}
              tickFormatter={(v: number) => formatCompact(v)}
            />
            <YAxis
              type="category"
              dataKey="x"
              {...axis}
              width={140}
              tickFormatter={(v: string) =>
                v.length > 20 ? v.slice(0, 19) + "…" : v
              }
            />
          </>
        ) : (
          <>
            <XAxis dataKey="x" {...axis} interval={0} />
            {valueAxis}
          </>
        )}
        <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
        {multi && (
          <ChartLegend itemSorter={null} content={<ChartLegendContent />} />
        )}
        {data.y.map((key) => (
          <Bar
            isAnimationActive={false}
            key={key}
            dataKey={key}
            fill={`var(--color-${key})`}
            radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
            maxBarSize={48}
          />
        ))}
      </BarChart>
    </ChartContainer>
  );
}
