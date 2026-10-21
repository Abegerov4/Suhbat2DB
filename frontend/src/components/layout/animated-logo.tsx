"use client";

import { motion, useReducedMotion } from "motion/react";

import { Logo } from "@/components/layout/logo";
import { cn } from "@/lib/utils";

/** Логотип, который медленно «парит» и мягко светится (страница входа, пустой чат). */
export function AnimatedLogo({ className }: { className?: string }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      aria-hidden
      className="relative"
      animate={reduced ? undefined : { y: [0, -8, 0] }}
      transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
    >
      <motion.div
        className="absolute inset-0 rounded-full bg-primary blur-2xl"
        animate={reduced ? { opacity: 0.3 } : { opacity: [0.2, 0.45, 0.2] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />
      <Logo className={cn("relative size-24", className)} />
    </motion.div>
  );
}
