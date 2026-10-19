"use client";

import {
  ChartColumn,
  Database,
  MessageSquare,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useRef, type RefObject } from "react";

import { Logo } from "@/components/layout/logo";
import { AnimatedBeam } from "@/components/ui/animated-beam";
import { cn } from "@/lib/utils";

const NODES: { label: string; icon?: LucideIcon; accent?: boolean }[] = [
  { label: "Вопрос", icon: MessageSquare },
  { label: "Агент", accent: true },
  { label: "Проверка SQL", icon: ShieldCheck },
  { label: "База данных", icon: Database },
  { label: "Ответ", icon: ChartColumn },
];

// SVG-атрибуты не понимают CSS-переменные — слоты 1 и 7 палитры графиков
const FROM = "#2a78d6";
const TO = "#6250d6";

/** Путь вопроса через платформу: лучи бегут от вопроса к ответу. */
export function PipelineBeam({ className }: { className?: string }) {
  const container = useRef<HTMLDivElement>(null);
  const r0 = useRef<HTMLDivElement>(null);
  const r1 = useRef<HTMLDivElement>(null);
  const r2 = useRef<HTMLDivElement>(null);
  const r3 = useRef<HTMLDivElement>(null);
  const r4 = useRef<HTMLDivElement>(null);
  const refs: RefObject<HTMLDivElement | null>[] = [r0, r1, r2, r3, r4];
  const reduced = useReducedMotion();

  return (
    <div
      ref={container}
      role="img"
      aria-label="Вопрос → агент → проверка SQL → база данных → ответ"
      className={cn(
        "relative flex w-full items-start justify-between",
        className,
      )}
    >
      {NODES.map((node, i) => (
        <div
          key={node.label}
          className="z-10 flex w-16 flex-col items-center gap-1.5"
        >
          <div
            ref={refs[i]}
            className={cn(
              "flex size-10 items-center justify-center rounded-full border bg-background shadow-sm",
              node.accent && "size-12 border-chart-1/40",
            )}
          >
            {node.icon ? (
              <node.icon className="size-4 text-muted-foreground" aria-hidden />
            ) : (
              <Logo className="size-7" />
            )}
          </div>
          <span className="text-center text-[11px] leading-tight text-muted-foreground">
            {node.label}
          </span>
        </div>
      ))}
      {NODES.slice(1).map((node, i) => (
        <AnimatedBeam
          key={node.label}
          containerRef={container}
          fromRef={refs[i]}
          toRef={refs[i + 1]}
          gradientStartColor={FROM}
          gradientStopColor={TO}
          pathColor="currentColor"
          pathOpacity={0.15}
          duration={3}
          delay={i * 0.5}
          // «уменьшить движение»: только линии, без бегущего света
          repeat={reduced ? 0 : Infinity}
          className="text-foreground"
        />
      ))}
    </div>
  );
}
