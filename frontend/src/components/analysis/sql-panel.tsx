"use client";

import { Check, CircleX, Copy, Wrench } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LEVEL_LABELS } from "@/components/analysis/validation-report";
import type { Attempt } from "@/lib/turn";
import { highlightSql } from "@/lib/highlight";

export function SqlCode({ sql }: { sql: string }) {
  const [html, setHtml] = useState<{ sql: string; html: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    highlightSql(sql)
      .then((h) => alive && setHtml({ sql, html: h }))
      .catch(() => alive && setHtml(null));
    return () => {
      alive = false;
    };
  }, [sql]);

  async function copy() {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="group relative rounded-lg border bg-muted/40">
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={copy}
        className="absolute top-1.5 right-1.5"
        aria-label={copied ? "Скопировано" : "Копировать SQL"}
      >
        {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
      </Button>
      {html?.sql === sql ? (
        <div
          className="overflow-x-auto p-3 pr-10 font-mono text-xs leading-relaxed [&_pre]:bg-transparent!"
          // HTML формирует shiki из текста SQL: все символы экранированы
          dangerouslySetInnerHTML={{ __html: html.html }}
        />
      ) : (
        <pre className="overflow-x-auto p-3 pr-10 font-mono text-xs leading-relaxed">
          {sql}
        </pre>
      )}
    </div>
  );
}

/** SQL последней попытки и, если была самокоррекция, предыдущие попытки с причиной отказа. */
export function SqlPanel({ attempts }: { attempts: Attempt[] }) {
  const current = attempts.at(-1);
  if (!current) {
    return (
      <p className="text-sm text-muted-foreground">SQL ещё не сгенерирован.</p>
    );
  }
  const previous = attempts.slice(0, -1);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium">Итоговый запрос</p>
          {attempts.length > 1 && (
            <Badge variant="secondary" className="gap-1">
              <Wrench className="size-3" aria-hidden />
              попытка {current.attempt}
            </Badge>
          )}
        </div>
        <SqlCode sql={current.sql} />
      </div>
      {previous.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-sm font-medium">Самокоррекция</p>
          {previous.map((a) => {
            const failed = a.levels.find((l) => !l.passed);
            return (
              <div
                key={a.attempt}
                className="flex flex-col gap-2 rounded-lg border border-dashed p-3"
              >
                <p className="flex items-start gap-1.5 text-xs">
                  <CircleX
                    className="mt-px size-3.5 shrink-0 text-status-critical"
                    aria-hidden
                  />
                  <span>
                    Попытка {a.attempt} остановлена
                    {failed && (
                      <>
                        {" "}
                        на уровне «{LEVEL_LABELS[failed.name]}»:{" "}
                        {failed.message}
                        {failed.hint && (
                          <span className="text-muted-foreground">
                            {" "}
                            Подсказка: {failed.hint}
                          </span>
                        )}
                      </>
                    )}
                  </span>
                </p>
                <SqlCode sql={a.sql} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
