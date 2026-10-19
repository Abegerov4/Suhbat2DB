import { describe, expect, it } from "vitest";

import { readEvents, splitEvents, toAgentEvent } from "../sse";

const encoder = new TextEncoder();

function stream(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
}

async function collect(chunks: string[]) {
  const events = [];
  for await (const e of readEvents(stream(chunks))) events.push(e);
  return events;
}

describe("splitEvents", () => {
  it("keeps an unfinished event in the buffer", () => {
    const { events, rest } = splitEvents(
      'event: step\ndata: {"a":1}\n\nevent: sql\ndata: {',
    );
    expect(events).toEqual([{ event: "step", data: '{"a":1}' }]);
    expect(rest).toBe("event: sql\ndata: {");
  });

  it("handles CRLF, comments and multi-line data", () => {
    const { events } = splitEvents(
      ": ping\r\n\r\nevent: answer\r\ndata: a\r\ndata: b\r\n\r\n",
    );
    expect(events).toEqual([{ event: "answer", data: "a\nb" }]);
  });
});

describe("readEvents", () => {
  it("parses events split across chunks, including inside UTF-8 characters", async () => {
    const bytes = encoder.encode('event: answer\ndata: {"text":"Выручка"}\n\n');
    const cut = bytes.indexOf(0xd1) + 1; // между байтами кириллической буквы
    const raw = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(bytes.slice(0, cut));
        c.enqueue(bytes.slice(cut));
        c.close();
      },
    });
    const events = [];
    for await (const e of readEvents(raw)) events.push(e);
    expect(events).toEqual([{ event: "answer", data: { text: "Выручка" } }]);
  });

  it("skips unknown events and invalid JSON (forward compatibility)", async () => {
    const events = await collect([
      "event: future_event\ndata: {}\n\n",
      "event: sql\ndata: not-json\n\n",
      'event: done\ndata: {"awaiting_clarification":false}',
    ]);
    expect(events).toEqual([
      { event: "done", data: { awaiting_clarification: false } },
    ]);
  });
});

describe("toAgentEvent", () => {
  it("returns null for messages without a known type", () => {
    expect(toAgentEvent({ event: "message", data: "{}" })).toBeNull();
  });
});
