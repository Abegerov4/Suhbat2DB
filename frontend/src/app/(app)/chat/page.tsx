"use client";

import { Database } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Composer } from "@/components/chat/composer";
import { ExampleQuestions } from "@/components/chat/example-questions";
import { DatasourceStatusBadge } from "@/components/datasources/status-badge";
import { SiteHeader } from "@/components/layout/site-header";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { setPendingQuestion } from "@/lib/pending-question";
import { useCreateSession, useDatasources } from "@/lib/queries";

export default function NewChatPage() {
  const router = useRouter();
  const datasources = useDatasources();
  const createSession = useCreateSession();
  const [chosen, setChosen] = useState<string | null>(null);

  const ready = datasources.data?.filter((d) => d.status === "ready") ?? [];
  const datasourceId = chosen ?? ready[0]?.id ?? null;
  const datasource = datasources.data?.find((d) => d.id === datasourceId);

  function start(question: string) {
    if (!datasourceId) return;
    createSession.mutate(datasourceId, {
      onSuccess: (session) => {
        setPendingQuestion(session.id, question);
        router.push(`/chat/${session.id}`);
      },
      onError: (e) => toast.error(e.message),
    });
  }

  return (
    <div className="flex h-svh flex-col">
      <SiteHeader
        title="Новый диалог"
        description="Выберите источник и задайте вопрос"
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6 sm:px-6">
          {datasources.isPending ? (
            <Skeleton className="h-9 w-72" />
          ) : datasources.data?.length ? (
            <div className="flex flex-wrap items-center gap-3">
              <span
                className="text-sm text-muted-foreground"
                id="datasource-label"
              >
                Источник данных
              </span>
              <Select
                value={datasourceId ?? undefined}
                onValueChange={setChosen}
              >
                <SelectTrigger
                  className="w-72"
                  aria-labelledby="datasource-label"
                >
                  <SelectValue placeholder="Нет готовых источников" />
                </SelectTrigger>
                <SelectContent>
                  {datasources.data.map((d) => (
                    <SelectItem
                      key={d.id}
                      value={d.id}
                      disabled={d.status !== "ready"}
                    >
                      {d.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {datasource && (
                <DatasourceStatusBadge status={datasource.status} />
              )}
            </div>
          ) : (
            <Empty className="border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Database aria-hidden />
                </EmptyMedia>
                <EmptyTitle>Нет источников данных</EmptyTitle>
                <EmptyDescription>
                  Подключите базу PostgreSQL с ролью только для чтения.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button asChild>
                  <Link href="/datasources">Подключить источник</Link>
                </Button>
              </EmptyContent>
            </Empty>
          )}
          <ExampleQuestions
            onPick={start}
            disabled={!datasourceId || createSession.isPending}
          />
        </div>
      </div>
      <div className="border-t bg-background px-4 py-3 sm:px-6">
        <div className="mx-auto max-w-3xl">
          <Composer
            onSend={start}
            busy={createSession.isPending}
            disabled={!datasourceId}
          />
        </div>
      </div>
    </div>
  );
}
