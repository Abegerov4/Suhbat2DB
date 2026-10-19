"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { apiFetch, ApiError } from "@/lib/api/client";

type Mode = "login" | "register";

const TEXT = {
  login: {
    title: "Вход",
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

export function AuthForm({ mode }: { mode: Mode }) {
  const text = TEXT[mode];
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

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
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">
          <h1>{text.title}</h1>
        </CardTitle>
        <CardDescription>{text.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate={false}>
          <FieldGroup>
            {error && (
              <Alert variant="destructive" role="alert">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Field>
              <FieldLabel htmlFor="email">Email</FieldLabel>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="analyst@company.kz"
                required
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="password">Пароль</FieldLabel>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                minLength={8}
                maxLength={128}
                required
              />
              {mode === "register" && (
                <FieldDescription>Не меньше 8 символов</FieldDescription>
              )}
            </Field>
            <Field>
              <Button type="submit" disabled={pending}>
                {pending && <Spinner />}
                {text.submit}
              </Button>
              <FieldDescription className="text-center">
                {text.switchText}{" "}
                <Link href={text.switchHref}>{text.switchLink}</Link>
              </FieldDescription>
            </Field>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
