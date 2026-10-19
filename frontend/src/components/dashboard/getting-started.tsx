import { MessageSquarePlus } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const STEPS = [
  {
    title: "Задайте вопрос",
    text: "Обычным языком: «выручка по регионам за 2025 год».",
  },
  {
    title: "Ответьте на уточнение",
    text: "Если вопрос можно понять по-разному, агент спросит.",
  },
  {
    title: "Проверьте результат",
    text: "График, таблица, SQL и отчёт пяти уровней проверки.",
  },
];

/** Первые шаги — пока у пользователя нет ни одного вопроса. */
export function GettingStarted() {
  return (
    <Card>
      <CardContent className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <span className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-primary/10">
            <MessageSquarePlus className="size-6 text-brand-text" aria-hidden />
          </span>
          <div className="flex-1">
            <p className="text-xs font-semibold tracking-[0.14em] text-brand-text uppercase">
              От вопроса к ответу
            </p>
            <h2 className="mt-1 text-xl font-semibold">
              Начните первый диалог
            </h2>
            <p className="mt-1 max-w-xl text-sm text-muted-foreground">
              Демо-база с продажами в Казахстане уже подключена — можно
              спрашивать сразу.
            </p>
          </div>
          <Button asChild className="self-start sm:self-center">
            <Link href="/chat">Задать вопрос</Link>
          </Button>
        </div>
        <Separator />
        <ol className="grid gap-6 sm:grid-cols-3">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex gap-3">
              <span className="text-sm font-medium text-brand-text tabular-nums">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span>
                <span className="block text-sm font-medium">{step.title}</span>
                <span className="block text-xs text-muted-foreground">
                  {step.text}
                </span>
              </span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
