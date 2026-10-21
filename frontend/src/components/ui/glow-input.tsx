"use client";

import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useReducedMotion,
} from "motion/react";
import { type ComponentProps, type ReactNode, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Рамка с подсветкой, которая следует за курсором (по мотивам Aceternity UI).
 * Оборачивает любое поле: input, textarea или составной блок.
 */
export function GlowBorder({
  children,
  className,
  radius = 110,
}: {
  children: ReactNode;
  className?: string;
  radius?: number;
}) {
  const reduced = useReducedMotion();
  const [hovered, setHovered] = useState(false);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const size = hovered && !reduced ? radius : 0;
  const background = useMotionTemplate`radial-gradient(${size}px circle at ${x}px ${y}px, var(--primary), transparent 80%)`;

  return (
    <motion.div
      style={{ background }}
      onMouseMove={({ currentTarget, clientX, clientY }) => {
        const { left, top } = currentTarget.getBoundingClientRect();
        x.set(clientX - left);
        y.set(clientY - top);
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        "group/input rounded-lg p-0.5 transition duration-300",
        className,
      )}
    >
      {children}
    </motion.div>
  );
}

/** Поле ввода с подсветкой рамки за курсором. */
export function GlowInput({ className, ...props }: ComponentProps<"input">) {
  return (
    <GlowBorder>
      <input
        className={cn(
          "flex h-11 w-full rounded-md border-none bg-muted px-3 py-2 text-sm text-foreground shadow-[0_0_0_1px_var(--border)] transition duration-300 placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 group-hover/input:shadow-none",
          className,
        )}
        {...props}
      />
    </GlowBorder>
  );
}
