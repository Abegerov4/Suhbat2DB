"use client";

import { ArrowUp, Square } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { Textarea } from "@/components/ui/textarea";

const MAX = 2000;

/** Ввод вопроса: Enter — отправить, Shift+Enter — новая строка. */
export function Composer({
  onSend,
  onStop,
  busy,
  disabled,
  placeholder = "Спросите о данных…",
  hint,
}: {
  onSend: (text: string) => void;
  onStop?: () => void | Promise<void>;
  busy: boolean;
  disabled?: boolean;
  placeholder?: string;
  hint?: React.ReactNode;
}) {
  const [text, setText] = useState("");
  const canSend = text.trim().length > 0 && !busy && !disabled;

  function submit() {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  }

  return (
    <form
      className="flex flex-col gap-1.5"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="relative rounded-xl border bg-background shadow-xs focus-within:ring-2 focus-within:ring-ring/50">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, MAX))}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={placeholder}
          aria-label="Вопрос к данным"
          disabled={disabled}
          rows={2}
          className="max-h-48 min-h-14 resize-none border-0 bg-transparent pr-14 shadow-none focus-visible:ring-0 dark:bg-transparent"
        />
        <div className="absolute right-2 bottom-2">
          {busy ? (
            <Button
              type="button"
              size="icon-sm"
              variant="secondary"
              onClick={onStop}
              aria-label="Остановить ответ"
            >
              <Square className="fill-current" aria-hidden />
            </Button>
          ) : (
            <Button
              type="submit"
              size="icon-sm"
              disabled={!canSend}
              aria-label="Отправить"
            >
              <ArrowUp aria-hidden />
            </Button>
          )}
        </div>
      </div>
      <p className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-muted-foreground">
        <span>
          {hint ?? (
            <>
              <Kbd>Enter</Kbd> отправить · <Kbd>Shift</Kbd>+<Kbd>Enter</Kbd>{" "}
              новая строка
            </>
          )}
        </span>
        {text.length > MAX * 0.8 && (
          <span className="tabular">
            {text.length}/{MAX}
          </span>
        )}
      </p>
    </form>
  );
}
