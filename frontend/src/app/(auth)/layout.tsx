import { AuthShowcase } from "@/components/auth-showcase";
import { Logo } from "@/components/layout/logo";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      {/* декоративная панель с орбитами: только на широких экранах */}
      <aside className="relative hidden bg-muted/50 lg:block dark:bg-white/[0.03]">
        <AuthShowcase />
      </aside>

      <main className="flex flex-col items-center justify-center px-6 py-10 sm:px-[10%]">
        <div className="flex w-full max-w-sm flex-col gap-8">
          <div className="flex items-center gap-2 font-semibold lg:hidden">
            <Logo className="size-8" />
            Suhbat2DB
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
