/**
 * Разбор потока text/event-stream. Стандартный EventSource не умеет POST,
 * поэтому поток читается через fetch и ReadableStream.
 */
import type { AgentEvent } from "./api/types";

export type RawEvent = { event: string; data: string };

/** Делит буфер на завершённые события (разделитель — пустая строка). */
export function splitEvents(buffer: string): {
  events: RawEvent[];
  rest: string;
} {
  const normalized = buffer.replace(/\r\n?/g, "\n");
  const blocks = normalized.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: RawEvent[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith(":")) continue; // комментарий / keep-alive
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      let value = colon === -1 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "event") event = value;
      else if (field === "data") data.push(value);
    }
    if (data.length) events.push({ event, data: data.join("\n") });
  }
  return { events, rest };
}

const KNOWN = new Set([
  "step",
  "clarification",
  "sql",
  "validation",
  "result",
  "answer",
  "chart",
  "error",
  "done",
]);

/** Неизвестные события пропускаются: совместимость вперёд (CONTRACTS §2). */
export function toAgentEvent(raw: RawEvent): AgentEvent | null {
  if (!KNOWN.has(raw.event)) return null;
  try {
    return { event: raw.event, data: JSON.parse(raw.data) } as AgentEvent;
  } catch {
    return null;
  }
}

export async function* readEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<AgentEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }); // UTF-8 на границе чанков
      const { events, rest } = splitEvents(buffer);
      buffer = rest;
      for (const raw of events) {
        const event = toAgentEvent(raw);
        if (event) yield event;
      }
    }
    const { events } = splitEvents(buffer + decoder.decode() + "\n\n");
    for (const raw of events) {
      const event = toAgentEvent(raw);
      if (event) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}
