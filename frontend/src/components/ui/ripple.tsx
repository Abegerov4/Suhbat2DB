import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/** Концентрические «дышащие» круги для фона (по мотивам Magic UI). */
export function Ripple({
  className,
  mainCircleSize = 180,
  mainCircleOpacity = 0.22,
  numCircles = 7,
}: {
  className?: string;
  mainCircleSize?: number;
  mainCircleOpacity?: number;
  numCircles?: number;
}) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 [mask-image:radial-gradient(circle,black_35%,transparent_70%)]",
        className,
      )}
    >
      {Array.from({ length: numCircles }, (_, i) => (
        <div
          key={i}
          style={
            {
              width: mainCircleSize + i * 70,
              height: mainCircleSize + i * 70,
              opacity: mainCircleOpacity - i * 0.03,
              "--i": i,
            } as CSSProperties
          }
          className="absolute top-1/2 left-1/2 animate-ripple rounded-full border border-primary/40 bg-primary/10 motion-reduce:animate-none motion-reduce:-translate-1/2"
        />
      ))}
    </div>
  );
}
