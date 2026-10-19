import { describe, expect, it } from "vitest";

import type { AgentEvent, Message } from "../api/types";
import { applyEvent, emptyTurn, hasAnalysis, turnFromMessage } from "../turn";

const run = (events: AgentEvent[]) => events.reduce(applyEvent, emptyTurn());

const failedSchema = {
  level: 3,
  name: "schema",
  passed: false,
  message: "Столбец amount не найден",
  hint: "Возможно, total_amount",
} as const;

describe("applyEvent", () => {
  it("tracks steps, self-correction attempts and the final answer", () => {
    const turn = run([
      { event: "step", data: { node: "generate_sql", status: "started" } },
      { event: "sql", data: { sql: "SELECT amount FROM orders", attempt: 1 } },
      { event: "validation", data: { level: 1, name: "syntax", passed: true } },
      { event: "validation", data: failedSchema },
      {
        event: "step",
        data: { node: "generate_sql", status: "finished", detail: "ok" },
      },
      {
        event: "sql",
        data: { sql: "SELECT total_amount FROM orders", attempt: 2 },
      },
      { event: "validation", data: { level: 1, name: "syntax", passed: true } },
      {
        event: "result",
        data: {
          columns: [],
          rows: [],
          row_count: 0,
          truncated: false,
          duration_ms: 3,
        },
      },
      { event: "answer", data: { text: "Готово" } },
      { event: "answer", data: { text: "." } },
      {
        event: "done",
        data: { message_id: "m1", awaiting_clarification: false },
      },
    ]);
    expect(turn.phase).toBe("done");
    expect(turn.id).toBe("m1");
    expect(turn.answer).toBe("Готово.");
    expect(turn.attempts.map((a) => a.attempt)).toEqual([1, 2]);
    expect(turn.attempts[0].levels.at(-1)?.hint).toBe("Возможно, total_amount");
    expect(turn.attempts[1].levels).toHaveLength(1);
    expect(turn.steps).toEqual([
      { node: "generate_sql", status: "done", detail: "ok" },
    ]);
    expect(hasAnalysis(turn)).toBe(true);
  });

  it("marks every step done when the stream ends", () => {
    const turn = run([
      { event: "step", data: { node: "guard_input", status: "started" } },
      { event: "error", data: { code: "refused", message: "Только чтение" } },
      { event: "done", data: { awaiting_clarification: false } },
    ]);
    expect(turn.steps[0].status).toBe("done");
    expect(turn.error?.code).toBe("refused");
    expect(hasAnalysis(turn)).toBe(false);
  });

  it("ignores validation before any SQL", () => {
    const turn = run([{ event: "validation", data: failedSchema }]);
    expect(turn.attempts).toEqual([]);
  });
});

describe("turnFromMessage", () => {
  const base: Message = {
    id: "m1",
    role: "assistant",
    content: "Уточните период",
    created_at: "2026-10-19T10:00:00Z",
    clarification: {
      question: "Уточните период",
      ambiguities: [
        {
          id: "q",
          type: "temporal",
          span: "квартал",
          options: [
            { id: "a", label: "Календарный" },
            { id: "b", label: "Финансовый" },
          ],
        },
      ],
    },
  };

  it("keeps a clarification active only on the last message", () => {
    expect(turnFromMessage(base, true).awaitingClarification).toBe(true);
    expect(turnFromMessage(base, false).awaitingClarification).toBe(false);
    expect(turnFromMessage(base, true).answer).toBe("");
  });

  it("restores SQL and validation as a single attempt", () => {
    const turn = turnFromMessage(
      {
        ...base,
        clarification: null,
        content: "Ответ",
        sql: "SELECT 1",
        validation_report: {
          passed: true,
          levels: [{ level: 1, name: "syntax", passed: true }],
        },
      },
      true,
    );
    expect(turn.answer).toBe("Ответ");
    expect(turn.attempts).toEqual([
      {
        attempt: 1,
        sql: "SELECT 1",
        levels: [{ level: 1, name: "syntax", passed: true }],
      },
    ]);
  });
});
