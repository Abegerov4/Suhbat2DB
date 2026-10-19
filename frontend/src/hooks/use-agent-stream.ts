"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";

import { ApiError, apiFetch } from "@/lib/api/client";
import type { ClarificationAnswer } from "@/lib/api/types";
import { keys, refreshAfterTurn } from "@/lib/queries";
import { readEvents } from "@/lib/sse";
import { applyEvent, emptyTurn, type Turn } from "@/lib/turn";

export type LiveTurn = {
  /** вопрос пользователя (у продолжения после уточнения — текст ответа) */
  question: string;
  turn: Turn;
};

/**
 * Поток ответа агента: POST → SSE → состояние хода (reducer по событиям).
 * Ход выполняется на бэкенде независимо от соединения: при уходе со страницы
 * ответ дописывается и сохраняется в историю. Остановить его — POST /stop.
 * Завершённые ходы сохраняются по id сообщения: в истории у них остаются
 * шаги агента и все попытки самокоррекции, которых нет в сохранённом сообщении.
 */
export function useAgentStream(sessionId: string) {
  const client = useQueryClient();
  const [live, setLive] = useState<LiveTurn | null>(null);
  const [finished, setFinished] = useState<Record<string, Turn>>({});
  const abort = useRef<AbortController | null>(null);
  const lastRequest = useRef<{
    path: string;
    body: unknown;
    question: string;
  } | null>(null);

  const run = useCallback(
    async (path: string, body: unknown, question: string) => {
      abort.current?.abort();
      lastRequest.current = { path, body, question };
      const controller = new AbortController();
      abort.current = controller;
      let turn = emptyTurn();
      setLive({ question, turn });

      try {
        const response = await apiFetch(path, {
          method: "POST",
          body: JSON.stringify(body),
          headers: { Accept: "text/event-stream" },
          signal: controller.signal,
        });
        // бэкенд уже сохранил вопрос и назвал им новый диалог
        client.invalidateQueries({ queryKey: keys.sessions, exact: true });
        for await (const event of readEvents(response.body!)) {
          turn = applyEvent(turn, event);
          setLive({ question, turn });
        }
        if (turn.phase !== "done") {
          turn = {
            ...turn,
            phase: "interrupted",
            error: turn.error ?? {
              code: "connection_lost",
              message: "Соединение прервалось до конца ответа",
            },
          };
          setLive({ question, turn });
          return;
        }
      } catch (e) {
        if (controller.signal.aborted) {
          turn = { ...turn, phase: "interrupted" };
          setLive({ question, turn });
          refreshAfterTurn(client, sessionId);
          return;
        }
        if (e instanceof ApiError) {
          // запрос отклонён до начала потока (409, 422…): вопрос не сохранён
          setLive(null);
          toast.error(e.message);
          return;
        }
        turn = {
          ...turn,
          phase: "interrupted",
          error: {
            code: "connection_lost",
            message: "Соединение с сервером прервалось",
          },
        };
        setLive({ question, turn });
        return;
      } finally {
        if (abort.current === controller) abort.current = null;
      }

      if (turn.id) setFinished((f) => ({ ...f, [turn.id!]: turn }));
      await client.refetchQueries({ queryKey: ["sessions", sessionId] });
      refreshAfterTurn(client, sessionId);
      setLive(null);
    },
    [client, sessionId],
  );

  const send = useCallback(
    (content: string) =>
      run(`/sessions/${sessionId}/messages`, { content }, content),
    [run, sessionId],
  );

  const clarify = useCallback(
    (answers: ClarificationAnswer[], summary: string) =>
      run(`/sessions/${sessionId}/clarify`, { answers }, summary),
    [run, sessionId],
  );

  // Бэкенд отменяет ход и сохраняет его с ошибкой cancelled — поток закончится сам.
  // Обрыв fetch — только запасной путь: без /stop ход дописался бы в фоне.
  const stop = useCallback(async () => {
    try {
      await apiFetch(`/sessions/${sessionId}/stop`, { method: "POST" });
    } catch {
      abort.current?.abort();
    }
  }, [sessionId]);
  const retry = useCallback(() => {
    const last = lastRequest.current;
    if (last) void run(last.path, last.body, last.question);
  }, [run]);
  const dismiss = useCallback(() => setLive(null), []);

  return {
    live,
    finished,
    busy: live?.turn.phase === "streaming",
    send,
    clarify,
    stop,
    retry,
    dismiss,
  };
}
