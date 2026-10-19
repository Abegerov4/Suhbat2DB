import { Logo } from "@/components/layout/logo";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted/40 p-4 sm:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex items-center gap-2 self-center font-semibold">
          <Logo className="size-7" />
          Suhbat2DB
        </div>
        {children}
        <p className="px-6 text-center text-xs text-balance text-muted-foreground">
          Вопросы к базе данных на естественном языке. Агент уточняет
          неоднозначности и проверяет каждый SQL перед выполнением.
        </p>
      </div>
    </div>
  );
}
