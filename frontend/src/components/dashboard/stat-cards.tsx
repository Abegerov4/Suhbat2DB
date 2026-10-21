import {
  CircleCheck,
  MessageCircleQuestion,
  MessagesSquare,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Skeleton } from "@/components/ui/skeleton";
import { type Tone, ToneIcon } from "@/components/ui/tone-icon";
import type { Stats } from "@/lib/api/types";
import { formatNumber, percent, plural } from "@/lib/format";

type Stat = {
  label: string;
  value: number;
  hint: string;
  icon: LucideIcon;
  tone: Tone;
};

function toStats(s: Stats): Stat[] {
  const turns = s.answered + s.clarifications + s.refused;
  const queries = s.queries_ok + s.queries_blocked + s.queries_failed;
  return [
    {
      label: "Вопросов задано",
      value: s.questions,
      hint: `в ${s.sessions} ${plural(s.sessions, ["диалоге", "диалогах", "диалогах"])}`,
      icon: MessagesSquare,
      tone: 1,
    },
    {
      label: "Ответов с данными",
      value: s.answered,
      hint: `${percent(s.answered, turns)}% ходов агента`,
      icon: CircleCheck,
      tone: 3,
    },
    {
      label: "Уточнений",
      value: s.clarifications,
      hint: "агент переспросил неоднозначный вопрос",
      icon: MessageCircleQuestion,
      tone: 4,
    },
    {
      label: "SQL заблокировано",
      value: s.queries_blocked,
      hint: `из ${formatNumber(queries)} проверенных запросов`,
      icon: ShieldCheck,
      tone: 8,
    },
  ];
}

export function StatCards({ stats }: { stats?: Stats }) {
  if (!stats) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-[118px] rounded-xl" />
        ))}
      </div>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {toStats(stats).map((stat) => (
        <Card key={stat.label}>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-medium">{stat.label}</CardTitle>
            <ToneIcon icon={stat.icon} tone={stat.tone} className="size-9" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">
              {/* счётчик для глаз; итоговое значение — для скринридера */}
              <NumberTicker value={stat.value} aria-hidden />
              <span className="sr-only">{formatNumber(stat.value)}</span>
            </p>
            <p className="text-xs text-muted-foreground">{stat.hint}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
