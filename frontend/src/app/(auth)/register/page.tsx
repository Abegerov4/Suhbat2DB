import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Регистрация" };

export default function Page() {
  // useSearchParams (параметр next) читается только на клиенте
  return (
    <Suspense>
      <AuthForm mode="register" />
    </Suspense>
  );
}
