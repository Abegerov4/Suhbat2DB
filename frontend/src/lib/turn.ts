/**
 * Ход ассистента: одна модель для живого потока (события SSE) и для истории
 * (сохранённое сообщение), чтобы чат и аналитическая панель рендерили их одинаково.
 */
import type {
  AgentError,
  AgentEvent,
  ChartSpec,
  ClarificationRequest,
  Message,
  NodeName,
  QueryResult,
  ValidationLevelResult,
} from "./api/types";

export type StepState = {
  node: NodeName;
  status: "running" | "done";
  detail?: string | null;
};

export type Attempt = {
  attempt: number;
  sql: string;
  levels: ValidationLevelResult[];
};

export type Turn = {
  /** стабильный ключ для UI: не меняется, когда живой ход получает id и уходит в историю */
  key: string;
  /** id сообщения ассистента; у живого потока появляется с событием done */
  id?: string;
  phase: "streaming" | "done" | "interrupted";
  steps: StepState[];
  attempts: Attempt[];
  result?: QueryResult;
  answer: string;
  chart?: ChartSpec;
  clarification?: ClarificationRequest;
  error?: AgentError;
  traceId?: string | null;
  awaitingClarification: boolean;
  createdAt?: string;
};

let runs = 0;

export const emptyTurn = (): Turn => ({
  key: `run-${++runs}`,
  phase: "streaming",
  steps: [],
  attempts: [],
  answer: "",
  awaitingClarification: false,
});

export function applyEvent(turn: Turn, e: AgentEvent): Turn {
  switch (e.event) {
    case "step": {
      const steps = [...turn.steps];
      const last = steps.findLastIndex((s) => s.node === e.data.node);
      if (e.data.status === "started" || last === -1) {
        steps.push({
          node: e.data.node,
          status: e.data.status === "started" ? "running" : "done",
          detail: e.data.detail,
        });
      } else {
        steps[last] = { ...steps[last], status: "done", detail: e.data.detail };
      }
      return { ...turn, steps };
    }
    case "sql":
      return {
        ...turn,
        attempts: [
          ...turn.attempts,
          { attempt: e.data.attempt, sql: e.data.sql, levels: [] },
        ],
        result: undefined,
      };
    case "validation": {
      const attempts = [...turn.attempts];
      const current = attempts.at(-1);
      if (!current) return turn;
      attempts[attempts.length - 1] = {
        ...current,
        levels: [
          ...current.levels.filter((l) => l.level !== e.data.level),
          e.data,
        ],
      };
      return { ...turn, attempts };
    }
    case "result":
      return { ...turn, result: e.data };
    case "answer":
      return { ...turn, answer: turn.answer + e.data.text };
    case "chart":
      return { ...turn, chart: e.data };
    case "clarification":
      return { ...turn, clarification: e.data };
    case "error":
      return { ...turn, error: e.data };
    case "done":
      return {
        ...turn,
        phase: "done",
        id: e.data.message_id ?? turn.id,
        traceId: e.data.trace_id,
        awaitingClarification: e.data.awaiting_clarification,
        steps: turn.steps.map((s) => ({ ...s, status: "done" })),
      };
  }
}

/** Сохранённое сообщение ассистента → ход (без шагов и прошлых попыток). */
export function turnFromMessage(m: Message, isLast: boolean): Turn {
  const levels = m.validation_report?.levels ?? [];
  return {
    key: m.id,
    id: m.id,
    phase: "done",
    steps: [],
    attempts: m.sql ? [{ attempt: 1, sql: m.sql, levels }] : [],
    result: m.result ?? undefined,
    answer: m.clarification || m.error ? "" : m.content,
    chart: m.chart_spec ?? undefined,
    clarification: m.clarification ?? undefined,
    error: m.error ?? undefined,
    traceId: m.trace_id,
    // незавершённое уточнение остаётся активным только у последнего сообщения
    awaitingClarification: Boolean(m.clarification) && isLast,
    createdAt: m.created_at,
  };
}

export const lastAttempt = (turn: Turn): Attempt | undefined =>
  turn.attempts.at(-1);

/** Ход содержит что показать в аналитической панели. */
export const hasAnalysis = (turn: Turn) =>
  turn.attempts.length > 0 || Boolean(turn.result);

export const STEP_LABELS: Record<NodeName, string> = {
  guard_input: "Проверяю запрос",
  schema_linking: "Ищу нужные таблицы",
  detect_ambiguity: "Проверяю однозначность",
  clarify: "Готовлю уточнение",
  generate_sql: "Генерирую SQL",
  validate_sql: "Проверяю SQL",
  self_correct: "Исправляю SQL",
  execute: "Выполняю запрос",
  explain_and_visualize: "Готовлю ответ",
  refuse: "Формирую отказ",
};
