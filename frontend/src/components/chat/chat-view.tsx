"use client";

import {
  MessageSquarePlus,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { AnalysisPanel } from "@/components/analysis/analysis-panel";
import { SiteHeader } from "@/components/layout/site-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useAgentStream } from "@/hooks/use-agent-stream";
import { useIsMobile } from "@/hooks/use-mobile";
import type { Message } from "@/lib/api/types";
import { takePendingQuestion } from "@/lib/pending-question";
import { useDatasources, useMessages, useSessions } from "@/lib/queries";
import { hasAnalysis, turnFromMessage, type Turn } from "@/lib/turn";

import { AnswerCard } from "./answer-card";
import { Composer } from "./composer";
import { ExampleQuestions } from "./example-questions";

const CLARIFICATION_PREFIX = "Уточнение: ";

type Row =
  | { kind: "user"; key: string; text: string }
  | {
      kind: "assistant";
      key: string;
      turn: Turn;
      question?: string;
      live: boolean;
    };

/** Исходный вопрос хода: ответ на уточнение продолжает предыдущий вопрос. */
function originalQuestion(texts: string[]): string | undefined {
  return (
    texts.findLast((t) => !t.startsWith(CLARIFICATION_PREFIX)) ?? texts.at(-1)
  );
}

function buildRows(
  messages: Message[],
  finished: Record<string, Turn>,
  live: ReturnType<typeof useAgentStream>["live"],
): Row[] {
  const rows: Row[] = [];
  const asked: string[] = [];
  messages.forEach((m, i) => {
    if (m.role === "user") {
      asked.push(m.content);
      rows.push({ kind: "user", key: m.id, text: m.content });
    } else {
      const isLast = i === messages.length - 1 && !live;
      const done = finished[m.id];
      // уточнение активно, только пока оно последнее сообщение диалога
      const turn = done
        ? {
            ...done,
            awaitingClarification: done.awaitingClarification && isLast,
          }
        : turnFromMessage(m, isLast);
      rows.push({
        kind: "assistant",
        key: turn.key, // тот же ключ, что был у живого хода: выбор в панели сохраняется
        turn,
        question: originalQuestion(asked),
        live: false,
      });
    }
  });
  if (live) {
    asked.push(live.question);
    rows.push({ kind: "user", key: "live-question", text: live.question });
    rows.push({
      kind: "assistant",
      key: live.turn.key,
      turn: live.turn,
      question: originalQuestion(asked),
      live: true,
    });
  }
  return rows;
}

export function ChatView({ sessionId }: { sessionId: string }) {
  const messages = useMessages(sessionId);
  const sessions = useSessions();
  const datasources = useDatasources();
  const stream = useAgentStream(sessionId);
  const isMobile = useIsMobile();

  const [selected, setSelected] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  const session = sessions.data?.find((s) => s.id === sessionId);
  const datasource = datasources.data?.find(
    (d) => d.id === session?.datasource_id,
  );
  const rows = useMemo(
    () => buildRows(messages.data ?? [], stream.finished, stream.live),
    [messages.data, stream.finished, stream.live],
  );
  const assistantRows = rows.filter((r) => r.kind === "assistant");
  const awaiting = assistantRows.at(-1)?.turn.awaitingClarification ?? false;

  // без явного выбора панель следует за последним ответом с данными
  // во время ответа — живой ход (подробный ход работы агента в панели)
  const auto = assistantRows.findLast(
    (r) => (r.live && r.turn.phase === "streaming") || hasAnalysis(r.turn),
  );
  const current =
    (selected && assistantRows.find((r) => r.key === selected)) || auto || null;

  // автопрокрутка, только если пользователь у нижнего края ленты
  const liveTurn = stream.live?.turn;
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 160) {
      el.scrollTo({ top: el.scrollHeight });
    }
  }, [rows.length, liveTurn]);

  useEffect(() => {
    const el = scroller.current;
    if (messages.isSuccess && el) el.scrollTo({ top: el.scrollHeight });
  }, [messages.isSuccess, sessionId]);

  // первый вопрос, заданный на странице /chat до создания сессии
  const { send: sendQuestion } = stream;
  useEffect(() => {
    const question = takePendingQuestion(sessionId);
    if (question) void sendQuestion(question);
  }, [sessionId, sendQuestion]);

  function select(key: string) {
    setSelected(key);
    if (isMobile) setSheetOpen(true);
    else setPanelOpen(true);
  }

  function send(text: string) {
    setSelected(null);
    void stream.send(text);
  }

  const notReady = datasource && datasource.status !== "ready";
  const empty = messages.isSuccess && rows.length === 0;

  const chat = (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6 sm:px-6">
          {messages.isPending && (
            <div className="flex flex-col gap-4">
              <Skeleton className="ml-auto h-10 w-2/3" />
              <Skeleton className="h-24 w-full" />
            </div>
          )}
          {messages.isError && (
            <Alert variant="destructive">
              <AlertDescription>{messages.error.message}</AlertDescription>
            </Alert>
          )}
          {empty && (
            <ExampleQuestions onPick={send} disabled={Boolean(notReady)} />
          )}
          {rows.map((row) =>
            row.kind === "user" ? (
              <div key={row.key} className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm whitespace-pre-wrap text-primary-foreground">
                  {row.text}
                </p>
              </div>
            ) : (
              <AnswerCard
                key={row.key}
                turn={row.turn}
                selected={current?.key === row.key}
                onSelect={() => select(row.key)}
                onClarify={(answers, summary) => {
                  setSelected(null);
                  void stream.clarify(answers, CLARIFICATION_PREFIX + summary);
                }}
                onRetry={
                  row.live && row.turn.phase === "interrupted"
                    ? stream.retry
                    : undefined
                }
              />
            ),
          )}
        </div>
      </div>
      <div className="border-t bg-background px-4 py-3 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <Composer
            onSend={send}
            onStop={stream.stop}
            busy={stream.busy}
            disabled={awaiting || Boolean(notReady)}
            placeholder={
              awaiting
                ? "Сначала ответьте на уточнение выше"
                : notReady
                  ? "Источник данных ещё не готов"
                  : undefined
            }
          />
        </div>
      </div>
    </div>
  );

  const panel = (
    <AnalysisPanel turn={current?.turn ?? null} question={current?.question} />
  );

  return (
    <div className="flex h-svh flex-col">
      <SiteHeader
        title={session?.title ?? "Диалог"}
        description={datasource ? `Источник: ${datasource.name}` : undefined}
      >
        {!isMobile && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setPanelOpen((o) => !o)}
            aria-label={
              panelOpen ? "Скрыть панель анализа" : "Показать панель анализа"
            }
            aria-pressed={panelOpen}
          >
            {panelOpen ? (
              <PanelRightClose aria-hidden />
            ) : (
              <PanelRightOpen aria-hidden />
            )}
          </Button>
        )}
        <Button variant="outline" size="sm" asChild>
          <Link href="/chat" aria-label="Новый диалог">
            <MessageSquarePlus aria-hidden />
            <span className="hidden sm:inline">Новый</span>
          </Link>
        </Button>
      </SiteHeader>

      <div className="min-h-0 flex-1">
        {isMobile || !panelOpen ? (
          chat
        ) : (
          <ResizablePanelGroup orientation="horizontal" id="chat-layout">
            <ResizablePanel id="chat" defaultSize="55%" minSize="35%">
              {chat}
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel id="analysis" defaultSize="45%" minSize="30%">
              <section
                aria-label="Панель анализа"
                className="h-full bg-muted/20"
              >
                {panel}
              </section>
            </ResizablePanel>
          </ResizablePanelGroup>
        )}
      </div>

      {isMobile && (
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetContent
            side="bottom"
            className="gap-0 p-0 data-[side=bottom]:h-[90svh]"
          >
            <SheetHeader className="sr-only">
              <SheetTitle>Анализ ответа</SheetTitle>
              <SheetDescription>
                График, таблица, SQL и проверка
              </SheetDescription>
            </SheetHeader>
            {panel}
          </SheetContent>
        </Sheet>
      )}
    </div>
  );
}
