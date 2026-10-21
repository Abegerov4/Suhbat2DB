"use client";

import { ArrowRight, Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { BoxReveal } from "@/components/ui/box-reveal";
import { GlowInput } from "@/components/ui/glow-input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { apiFetch, ApiError } from "@/lib/api/client";

type Mode = "login" | "register";

const TEXT = {
  login: {
    title: "С возвращением",
    description: "Войдите, чтобы задавать вопросы к данным",
    submit: "Войти",
    switchText: "Нет аккаунта?",
    switchLink: "Зарегистрироваться",
    switchHref: "/register",
  },
  register: {
    title: "Регистрация",
    description: "Новый аккаунт получает роль аналитика",
    submit: "Создать аккаунт",
    switchText: "Уже есть аккаунт?",
    switchLink: "Войти",
    switchHref: "/login",
  },
} as const;

/** Только относительный путь внутри приложения: защита от open redirect. */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

async function login(email: string, password: string) {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      body.error?.code ?? "http_error",
      body.error?.message ?? "Не удалось войти",
    );
  }
}

/** Градиентная полоса под кнопкой при наведении. */
function BottomGradient() {
  return (
    <>
      <span className="absolute inset-x-0 -bottom-px block h-px w-full bg-gradient-to-r from-transparent via-cyan-300 to-transparent opacity-0 transition duration-500 group-hover/btn:opacity-100" />
      <span className="absolute inset-x-10 -bottom-px mx-auto block h-px w-1/2 bg-gradient-to-r from-transparent via-white to-transparent opacity-0 blur-sm transition duration-500 group-hover/btn:opacity-100" />
    </>
  );
}

function RequiredMark() {
  return (
    <span aria-hidden className="text-destructive">
      *
    </span>
  );
}

export function AuthForm({ mode }: { mode: Mode }) {
  const text = TEXT[mode];
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    setPending(true);
    setError(null);
    try {
      if (mode === "register") {
        await apiFetch("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
      }
      await login(email, password);
      // полная загрузка: маршруты, сохранённые до входа, перезапрашиваются уже с cookie
      window.location.replace(safeNext(params.get("next")));
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.code === "validation_error"
            ? "Проверьте email и длину пароля (не меньше 8 символов)"
            : e.message
          : "Сервер недоступен",
      );
      setPending(false);
    }
  }

  return (
    <div className="flex w-full flex-col gap-4">
      <BoxReveal>
        <h1 className="text-3xl font-bold tracking-tight">{text.title}</h1>
      </BoxReveal>
      <BoxReveal delay={0.05} className="pb-2">
        <p className="text-sm text-muted-foreground">{text.description}</p>
      </BoxReveal>

      <form onSubmit={onSubmit} className="flex flex-col gap-5">
        {error && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col gap-2">
          <BoxReveal delay={0.1}>
            <Label htmlFor="email">
              Email <RequiredMark />
            </Label>
          </BoxReveal>
          <BoxReveal delay={0.12}>
            <GlowInput
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="analyst@company.kz"
              required
            />
          </BoxReveal>
        </div>

        <div className="flex flex-col gap-2">
          <BoxReveal delay={0.15}>
            <Label htmlFor="password">
              Пароль <RequiredMark />
            </Label>
          </BoxReveal>
          <BoxReveal delay={0.17}>
            <div className="relative">
              <GlowInput
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                placeholder={
                  mode === "register" ? "Не меньше 8 символов" : undefined
                }
                minLength={8}
                maxLength={128}
                required
                className="pr-11"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-pressed={showPassword}
                title={showPassword ? "Скрыть символы" : "Показать символы"}
                className="absolute inset-y-0 right-0 flex items-center rounded-md px-3 text-muted-foreground transition hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                {showPassword ? (
                  <Eye className="size-5" aria-hidden />
                ) : (
                  <EyeOff className="size-5" aria-hidden />
                )}
                <span className="sr-only">
                  {showPassword ? "Скрыть символы" : "Показать символы"}
                </span>
              </button>
            </div>
          </BoxReveal>
        </div>

        <BoxReveal delay={0.2} className="pt-2">
          <button
            type="submit"
            disabled={pending}
            className="group/btn relative flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary font-medium text-primary-foreground shadow-[0_1px_0_0_#ffffff30_inset] transition hover:cursor-pointer hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-70"
          >
            {pending && <Spinner />}
            {text.submit}
            <ArrowRight className="size-4" aria-hidden />
            <BottomGradient />
          </button>
        </BoxReveal>

        <BoxReveal delay={0.25}>
          <p className="text-sm text-muted-foreground">
            {text.switchText}{" "}
            <Link
              href={text.switchHref}
              className="font-medium text-brand-text underline-offset-4 hover:underline"
            >
              {text.switchLink}
            </Link>
          </p>
        </BoxReveal>
      </form>
    </div>
  );
}
