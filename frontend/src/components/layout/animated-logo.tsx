"use client";

import { motion, useReducedMotion } from "motion/react";

import { Logo } from "@/components/layout/logo";
import { cn } from "@/lib/utils";

/**
 * Логотип, который медленно «парит» и мягко светится (страница входа, пустой чат).
 * При prefers-reduced-motion анимация не повторяется; разметка та же, что на сервере.
 */
export function AnimatedLogo({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  const loop = reduced
    ? { duration: 0 }
    : { duration: 4, repeat: Infinity, ease: "easeInOut" as const };
  return (
    <motion.div
      aria-hidden
      className="relative"
      animate={{ y: [0, -8, 0] }}
      transition={loop}
    >
      <motion.div
        className="absolute inset-0 rounded-full bg-primary blur-2xl"
        animate={{ opacity: [0.2, 0.45, 0.2] }}
        transition={loop}
      />
      <Logo className={cn("relative size-24", className)} />
    </motion.div>
  );
}
