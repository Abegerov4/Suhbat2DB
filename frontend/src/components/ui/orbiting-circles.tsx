import { Children, type CSSProperties, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Элементы, равномерно расставленные по окружности и вращающиеся вокруг центра
 * (по мотивам Magic UI). Родитель задаёт размеры и `position: relative`.
 * При prefers-reduced-motion анимация ставится на паузу: элементы остаются на орбите.
 */
export function OrbitingCircles({
  children,
  className,
  radius = 160,
  duration = 20,
  reverse = false,
  path = true,
  iconSize = 40,
}: {
  children: ReactNode;
  className?: string;
  radius?: number;
  /** секунд на полный оборот */
  duration?: number;
  reverse?: boolean;
  path?: boolean;
  iconSize?: number;
}) {
  const count = Children.count(children);
  return (
    <>
      {path && (
        <svg
          aria-hidden
          className="pointer-events-none absolute inset-0 size-full"
        >
          <circle
            className="fill-none stroke-border"
            strokeDasharray="4 6"
            cx="50%"
            cy="50%"
            r={radius}
          />
        </svg>
      )}
      {Children.map(children, (child, index) => (
        <div
          style={
            {
              "--duration": duration,
              "--radius": radius,
              "--angle": (360 / count) * index,
              "--icon-size": `${iconSize}px`,
            } as CSSProperties
          }
          className={cn(
            "absolute flex size-(--icon-size) transform-gpu animate-orbit items-center justify-center motion-reduce:[animation-play-state:paused]",
            reverse && "[animation-direction:reverse]",
            className,
          )}
        >
          {child}
        </div>
      ))}
    </>
  );
}
