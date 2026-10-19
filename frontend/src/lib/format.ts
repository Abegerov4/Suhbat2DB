const number = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
const compact = new Intl.NumberFormat("ru-RU", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const dateTime = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const day = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
});

const NUMERIC_TYPES =
  /^(int|smallint|bigint|integer|numeric|decimal|real|double|float|money)/i;
const TEMPORAL_TYPES = /^(date|timestamp|time)/i;

export const isNumericType = (type: string) => NUMERIC_TYPES.test(type);
export const isTemporalType = (type: string) => TEMPORAL_TYPES.test(type);

/** Значение ячейки результата: numeric приходит строкой (Decimal), дата — ISO. */
export function formatCell(value: unknown, type: string): string {
  if (value === null || value === undefined) return "—";
  if (isNumericType(type)) {
    const n = Number(value);
    return Number.isFinite(n) ? number.format(n) : String(value);
  }
  if (typeof value === "boolean") return value ? "да" : "нет";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export const formatNumber = (n: number) => number.format(n);
export const formatCompact = (n: number) =>
  Math.abs(n) >= 10_000 ? compact.format(n) : number.format(n);

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));
export const formatDay = (iso: string) => day.format(new Date(iso));

export function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms} мс` : `${(ms / 1000).toFixed(1)} с`;
}

export const percent = (part: number, total: number) =>
  total ? Math.round((part / total) * 100) : 0;

/** Склонение: plural(5, ["запрос", "запроса", "запросов"]) → «запросов». */
export function plural(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}

export const ROWS: [string, string, string] = ["строка", "строки", "строк"];
export const COLUMNS: [string, string, string] = [
  "столбец",
  "столбца",
  "столбцов",
];

/** «1 строка», «5 строк» с разделителями разрядов. */
export const countOf = (n: number, forms: [string, string, string]) =>
  `${formatNumber(n)} ${plural(n, forms)}`;
