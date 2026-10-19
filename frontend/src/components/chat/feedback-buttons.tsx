"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useFeedback } from "@/lib/queries";
import { cn } from "@/lib/utils";

/** 👍/👎 уходит в БД и в Langfuse (score user_feedback по trace_id ответа). */
export function FeedbackButtons({ messageId }: { messageId: string }) {
  const feedback = useFeedback();
  const [score, setScore] = useState<1 | -1 | null>(null);
  const [commenting, setCommenting] = useState(false);
  const [comment, setComment] = useState("");

  function send(value: 1 | -1, text?: string) {
    setScore(value);
    feedback.mutate(
      { messageId, score: value, comment: text || undefined },
      {
        onSuccess: () => {
          if (text) toast.success("Спасибо за комментарий");
        },
        onError: (e) => {
          setScore(null);
          toast.error(e.message);
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Полезный ответ"
          aria-pressed={score === 1}
          onClick={() => {
            setCommenting(false);
            send(1);
          }}
        >
          <ThumbsUp
            className={cn(score === 1 && "fill-current text-status-good")}
            aria-hidden
          />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Неполезный ответ"
          aria-pressed={score === -1}
          onClick={() => {
            send(-1);
            setCommenting(true);
          }}
        >
          <ThumbsDown
            className={cn(score === -1 && "fill-current text-status-critical")}
            aria-hidden
          />
        </Button>
      </div>
      {commenting && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send(-1, comment.trim());
            setCommenting(false);
          }}
        >
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Что не так с ответом? (необязательно)"
            maxLength={2000}
            rows={2}
            aria-label="Комментарий к оценке"
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={!comment.trim()}>
              Отправить
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setCommenting(false)}
            >
              Пропустить
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
