import { describe, expect, it } from "vitest";

import type { QueryResult } from "../api/types";
import { pieData, toChartData, toCsv } from "../chart";
import { formatCell, plural } from "../format";

const result: QueryResult = {
  columns: [
    { name: "регион", type: "varchar" },
    { name: "выручка", type: "numeric" },
    { name: "заказы", type: "int8" },
  ],
  rows: [
    ["Алматы", "1500.50", 10],
    ["Астана", null, 4],
  ],
  row_count: 2,
  truncated: false,
  duration_ms: 12,
};

describe("toChartData", () => {
  it("converts numeric strings and names series with safe keys", () => {
    const data = toChartData(result, {
      type: "bar",
      x: "регион",
      y: ["выручка", "заказы"],
    });
    expect(data?.rows).toEqual([
      { x: "Алматы", s0: 1500.5, s1: 10 },
      { x: "Астана", s0: null, s1: 4 },
    ]);
    expect(data?.config.s0).toEqual({
      label: "выручка",
      color: "var(--chart-1)",
    });
  });

  it("drops non-numeric y columns and returns null without a plot", () => {
    expect(
      toChartData(result, { type: "bar", x: "регион", y: ["регион"] }),
    ).toBeNull();
    expect(
      toChartData(result, { type: "none", x: "регион", y: ["выручка"] }),
    ).toBeNull();
    expect(
      toChartData(result, { type: "bar", x: "нет", y: ["выручка"] }),
    ).toBeNull();
  });

  it("formats month starts on the x axis", () => {
    const data = toChartData(
      {
        ...result,
        columns: [
          { name: "месяц", type: "timestamptz" },
          { name: "выручка", type: "numeric" },
        ],
        rows: [["2026-01-01T00:00:00+00:00", "1"]],
      },
      { type: "line", x: "месяц", y: ["выручка"] },
    );
    expect(String(data?.rows[0].x)).toMatch(/янв.*2026/);
  });

  it("gives each pie slice its own slot color", () => {
    const data = toChartData(result, {
      type: "pie",
      x: "регион",
      y: ["заказы"],
    })!;
    expect(pieData(data).map((s) => s.fill)).toEqual([
      "var(--chart-1)",
      "var(--chart-2)",
    ]);
  });
});

describe("toCsv", () => {
  it("adds BOM and escapes separators", () => {
    const csv = toCsv({
      ...result,
      rows: [['ТОО "Альфа", Алматы', "1", 2]],
    });
    expect(csv.startsWith("﻿регион,выручка,заказы\n")).toBe(true);
    expect(csv).toContain('"ТОО ""Альфа"", Алматы",1,2');
  });
});

describe("format", () => {
  it("formats cells by column type", () => {
    expect(formatCell("1500.5", "numeric").replace(/\s/g, " ")).toBe("1 500,5");
    expect(formatCell(null, "text")).toBe("—");
    expect(formatCell(true, "bool")).toBe("да");
  });

  it("declines Russian nouns", () => {
    const forms: [string, string, string] = ["строка", "строки", "строк"];
    expect([1, 2, 5, 11, 21, 104].map((n) => plural(n, forms))).toEqual([
      "строка",
      "строки",
      "строк",
      "строк",
      "строка",
      "строки",
    ]);
  });
});
