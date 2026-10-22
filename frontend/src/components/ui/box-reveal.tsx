"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Появление содержимого из-под сдвигающейся «шторки» (по мотивам Magic UI).
 * Разметка одинакова на сервере и клиенте: при prefers-reduced-motion меняется
 * только длительность (0), иначе гидратация расходится и React пересобирает дерево.
 */
export function BoxReveal({
  children,
  className,
  delay = 0,
  duration = 0.35,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  duration?: number;
}) {
  const reduced = useReducedMotion();
  const timing = reduced ? { duration: 0, delay: 0 } : { duration, delay };

  return (
    <div className={cn("relative overflow-hidden", className)}>
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: timing.duration,
          delay: reduced ? 0 : delay + 0.2,
        }}
      >
        {children}
      </motion.div>
      <motion.div
        aria-hidden
        initial={{ left: 0 }}
        animate={{ left: "100%" }}
        transition={{ ...timing, ease: "easeIn" }}
        className="absolute inset-y-1 right-0 z-20 rounded bg-primary/25"
      />
    </div>
  );
}
