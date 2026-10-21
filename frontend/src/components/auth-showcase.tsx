"use client";

import {
  ChartColumn,
  Database,
  DatabaseZap,
  FileCode2,
  FileSpreadsheet,
  FolderOpen,
  type LucideIcon,
  MessageSquareText,
  Server,
  ShieldCheck,
  Table2,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import { Logo } from "@/components/layout/logo";
import { OrbitingCircles } from "@/components/ui/orbiting-circles";
import { Ripple } from "@/components/ui/ripple";

/** Иконка на орбите; цвет — из категориальной палитры графиков. */
function OrbitIcon({ icon: Icon, tone }: { icon: LucideIcon; tone: number }) {
  return (
    <span
      style={{
        color: `var(--chart-${tone})`,
        background: `color-mix(in oklab, var(--chart-${tone}) 16%, var(--card))`,
        borderColor: `color-mix(in oklab, var(--chart-${tone}) 35%, transparent)`,
      }}
      className="flex size-full items-center justify-center rounded-2xl border shadow-lg backdrop-blur-sm"
    >
      <Icon className="size-1/2" strokeWidth={1.75} />
    </span>
  );
}

/** Логотип, который медленно «парит» и мягко светится. */
function AnimatedLogo() {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className="relative"
      animate={reduced ? undefined : { y: [0, -8, 0] }}
      transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
    >
      <motion.div
        aria-hidden
        className="absolute inset-0 rounded-full bg-primary blur-2xl"
        animate={reduced ? { opacity: 0.3 } : { opacity: [0.2, 0.45, 0.2] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />
      <Logo className="relative size-24" />
    </motion.div>
  );
}

/**
 * Левая панель страниц входа: логотип и название в центре, вокруг на орбитах
 * вращаются базы данных, таблицы и этапы обработки вопроса.
 */
export function AuthShowcase() {
  return (
    <div aria-hidden className="absolute inset-0 overflow-hidden">
      <Ripple mainCircleSize={160} numCircles={9} mainCircleOpacity={0.18} />

      <div className="absolute inset-0 flex items-center justify-center">
        <OrbitingCircles radius={140} duration={24} iconSize={44} path={false}>
          <OrbitIcon icon={Database} tone={1} />
          <OrbitIcon icon={Table2} tone={2} />
        </OrbitingCircles>
        <OrbitingCircles
          radius={210}
          duration={32}
          iconSize={50}
          path={false}
          reverse
        >
          <OrbitIcon icon={MessageSquareText} tone={3} />
          <OrbitIcon icon={FileCode2} tone={4} />
          <OrbitIcon icon={ShieldCheck} tone={5} />
        </OrbitingCircles>
        <OrbitingCircles radius={285} duration={44} iconSize={58} path={false}>
          <OrbitIcon icon={Server} tone={6} />
          <OrbitIcon icon={FolderOpen} tone={7} />
          <OrbitIcon icon={ChartColumn} tone={1} />
          <OrbitIcon icon={DatabaseZap} tone={8} />
          <OrbitIcon icon={FileSpreadsheet} tone={2} />
        </OrbitingCircles>
      </div>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-4">
        <AnimatedLogo />
        <span className="bg-gradient-to-b from-foreground to-foreground/30 bg-clip-text text-6xl leading-none font-semibold tracking-tight text-transparent xl:text-7xl">
          Suhbat2DB
        </span>
      </div>
    </div>
  );
}
