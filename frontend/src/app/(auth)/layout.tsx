import { Logo } from "@/components/layout/logo";
import { PipelineBeam } from "@/components/pipeline-beam";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="relative flex min-h-svh flex-col items-center justify-center gap-6 overflow-hidden bg-muted/40 p-4 sm:p-10">
      {/* точечный фон, затухающий к краям */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(var(--border)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)] bg-[size:18px_18px]"
      />
      <div className="relative flex w-full max-w-sm flex-col gap-6">
        <div className="flex items-center gap-2 self-center font-semibold">
          <Logo className="size-7" />
          Suhbat2DB
        </div>
        <PipelineBeam className="px-1" />
        {children}
        <p className="px-6 text-center text-xs text-balance text-muted-foreground">
          Вопросы к базе данных на естественном языке. Агент уточняет
          неоднозначности и проверяет каждый SQL перед выполнением.
        </p>
      </div>
    </div>
  );
}
