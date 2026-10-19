"use client";

import { animate, useReducedMotion } from "motion/react";
import {
  useEffect,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
} from "react";

import { cn } from "@/lib/utils";

const format = (n: number, decimals: number) =>
  new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Number(n.toFixed(decimals)));

interface NumberTickerProps extends ComponentPropsWithoutRef<"span"> {
  value: number;
  decimalPlaces?: number;
  /** длительность счёта, с */
  duration?: number;
}

/**
 * Анимированный счётчик (по мотивам Magic UI number-ticker). Число хранится в
 * состоянии React, а не пишется в DOM напрямую: оригинал оставлял «0», когда
 * Next 16 возвращал страницу, сохранённую в <Activity>.
 */
export function NumberTicker({
  value,
  decimalPlaces = 0,
  duration = 1,
  className,
  ...props
}: NumberTickerProps) {
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(0);
  const current = useRef(0);

  useEffect(() => {
    if (reduced) return;
    const controls = animate(current.current, value, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => {
        current.current = v;
        setDisplay(v);
      },
    });
    return () => controls.stop();
  }, [value, duration, reduced]);

  return (
    <span className={cn("inline-block tabular-nums", className)} {...props}>
      {format(reduced ? value : display, decimalPlaces)}
    </span>
  );
}
