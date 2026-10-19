import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/layout/page-skeleton";

import { ChatRoute } from "./chat-route";

export const metadata: Metadata = { title: "Диалог" };

export default function ChatPage() {
  // id сессии из URL доступен только во время запроса: оболочка отдаётся сразу
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ChatRoute />
    </Suspense>
  );
}
