import { useId } from "react";

import { cn } from "@/lib/utils";

/**
 * Логотип: облачко диалога + цилиндр БД с казахским орнаментом «қошқар мүйіз».
 * Исходник — docs/brand/Suhbat2DB_logo.svg. Белые разделители, точки и орнамент
 * сделаны маской, а не белой заливкой: в тёмной теме сквозь них видна подложка.
 */
export function Logo({ className }: { className?: string }) {
  const mask = `logo-cut-${useId().replace(/:/g, "")}`;
  return (
    // span-обёртка: кнопки меню shadcn принудительно уменьшают вложенные svg
    <span aria-hidden className={cn("flex size-8 shrink-0", className)}>
      {/* size-full!: перебивает [&_svg]:size-4 у кнопок меню */}
      <svg viewBox="84 88 356 356" className="size-full!">
        <mask id={mask}>
          <rect x="0" y="0" width="512" height="512" fill="#fff" />
          <g fill="none" stroke="#000" strokeLinecap="round">
            <path strokeWidth="11.5" d="M114 180 C151 242 372 242 410 180" />
            <path strokeWidth="11" d="M113 271 C157 321 365 321 411 271" />
          </g>
          <g fill="#000">
            <circle cx="215" cy="349" r="11" />
            <circle cx="262" cy="349" r="11" />
            <circle cx="309" cy="349" r="11" />
            <path d="M262 109 C245 130 242 143 249 158 Q255 169 262 178 Q269 169 275 158 C282 143 279 130 262 109 Z" />
            <path d="M260 163 Q243 145 223 145 Q216 145 206 151 Q231 150 249 177 L262 192 L275 177 Q293 150 318 151 Q308 145 301 145 Q281 145 264 163 Z" />
          </g>
          <g
            fill="none"
            stroke="#000"
            strokeWidth="14"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M262 203 C245 180 222 160 199 160 C180 160 170 176 180 188 C193 204 216 188 203 178" />
            <path d="M262 203 C279 180 302 160 325 160 C344 160 354 176 344 188 C331 204 308 188 321 178" />
          </g>
        </mask>
        <g mask={`url(#${mask})`}>
          <path
            fill="#2a78d6"
            d="M113 169 V338 C113 365 133 384 163 389 L147 428 Q141 444 155 436 L230 391 H332 C381 391 411 369 411 338 V169 Z"
          />
          <ellipse fill="#3987e5" cx="262" cy="169" rx="149" ry="68" />
        </g>
      </svg>
    </span>
  );
}
