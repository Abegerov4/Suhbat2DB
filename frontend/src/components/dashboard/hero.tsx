import { Plus, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";

/** Фирменный баннер «Обзора»: всегда тёмно-синий, в обеих темах. */
export function Hero() {
  return (
    <section
      aria-labelledby="hero-title"
      className="relative isolate overflow-hidden rounded-2xl border border-[#256abf]/40 bg-[linear-gradient(120deg,#0b2447_0%,#123f78_45%,#256abf_100%)] px-6 py-8 text-white shadow-sm sm:px-10 sm:py-10"
    >
      {/* свечение и крупный силуэт логотипа справа */}
      <div
        aria-hidden
        className="absolute -top-24 right-0 -z-10 size-96 rounded-full bg-[#5598e7]/30 blur-3xl"
      />
      <Logo
        mono
        className="absolute -right-10 -bottom-16 -z-10 hidden size-80 text-white/10 md:flex"
      />

      <p className="text-xs font-semibold tracking-[0.18em] text-[#cde2fb] uppercase">
        Suhbat2DB · Диалоговая аналитика
      </p>
      <h2
        id="hero-title"
        className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl"
      >
        Спросите данные словами
      </h2>
      <p className="mt-2 max-w-xl text-base text-[#e6f0fd] sm:text-lg">
        Агент уточнит неоднозначный вопрос, составит SQL и проверит его на пяти
        уровнях — до того как запрос коснётся базы.
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Button
          asChild
          size="lg"
          className="bg-white text-[#0b2447] hover:bg-white/90"
        >
          <Link href="/chat">
            <Plus aria-hidden />
            Новый диалог
          </Link>
        </Button>
        <span className="inline-flex items-center gap-1.5 text-sm text-[#e6f0fd]">
          <ShieldCheck className="size-4" aria-hidden />
          Только чтение · READ ONLY транзакции
        </span>
      </div>
    </section>
  );
}
