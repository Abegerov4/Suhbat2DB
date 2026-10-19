/**
 * QueryResult + ChartSpec → данные для Recharts. Тип графика выбирает бэкенд
 * (agent/charts.py); здесь только приведение типов и цвета серий.
 */
import type { ChartConfig } from "@/components/ui/chart";

import type { ChartSpec, QueryResult } from "./api/types";
import { isNumericType, isTemporalType } from "./format";

/** Порядок цветов фиксирован: цвет следует за серией, а не за её рангом. */
export const SERIES_COLORS = Array.from(
  { length: 8 },
  (_, i) => `var(--chart-${i + 1})`,
);

export type ChartData = {
  rows: Record<string, string | number | null>[];
  config: ChartConfig;
  x: string;
  y: string[];
};

/** Ключ серии для CSS-переменной --color-<key>: имена столбцов бывают кириллическими. */
export const seriesKey = (index: number) => `s${index}`;

export function toChartData(
  result: QueryResult,
  spec: ChartSpec,
): ChartData | null {
  const index = new Map(result.columns.map((c, i) => [c.name, i]));
  const xi = index.get(spec.x);
  const ys = spec.y.filter((name) => {
    const i = index.get(name);
    return i !== undefined && isNumericType(result.columns[i].type);
  });
  if (xi === undefined || ys.length === 0 || spec.type === "none") return null;

  const xType = result.columns[xi].type;
  const rows = result.rows.map((row) => {
    const point: Record<string, string | number | null> = {
      // у scatter ось X числовая, у остальных — подписи категорий или дат
      x: spec.type === "scatter" ? Number(row[xi]) : formatX(row[xi], xType),
    };
    ys.forEach((name, k) => {
      const v = row[index.get(name)!];
      point[seriesKey(k)] = v === null ? null : Number(v);
    });
    return point;
  });

  const config: ChartConfig = {};
  ys.forEach((name, k) => {
    config[seriesKey(k)] = {
      label: name,
      color: SERIES_COLORS[k % SERIES_COLORS.length],
    };
  });
  return {
    rows,
    config,
    x: "x",
    y: ys.map((_, k) => seriesKey(k)),
  };
}

function formatX(value: unknown, type: string): string {
  if (value === null || value === undefined) return "—";
  if (isTemporalType(type) && typeof value === "string") {
    const d = new Date(value);
    if (!Number.isNaN(d.getTime())) {
      const monthStart = d.getUTCDate() === 1 && d.getUTCHours() === 0;
      return d.toLocaleDateString("ru-RU", {
        timeZone: "UTC",
        ...(monthStart
          ? { month: "short", year: "numeric" }
          : { day: "numeric", month: "short", year: "2-digit" }),
      });
    }
  }
  return String(value);
}

/** Для pie: каждый сектор — отдельная категория со своим цветом слота. */
export function pieData(data: ChartData) {
  const key = data.y[0];
  return data.rows.map((row, i) => ({
    name: String(row.x),
    value: Number(row[key] ?? 0),
    fill: SERIES_COLORS[i % SERIES_COLORS.length],
  }));
}

/** CSV с BOM: Excel корректно открывает кириллицу. */
export function toCsv(result: QueryResult): string {
  const escape = (v: unknown) => {
    if (v === null || v === undefined) return "";
    const s = typeof v === "object" ? JSON.stringify(v) : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    result.columns.map((c) => escape(c.name)).join(","),
    ...result.rows.map((r) => r.map(escape).join(",")),
  ];
  return "﻿" + lines.join("\n");
}
