import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/layout/page-skeleton";

import { SchemaView } from "./schema-view";

export const metadata: Metadata = { title: "Схема" };

export default function SchemaPage() {
  // id из URL доступен только во время запроса: оболочка отдаётся сразу
  return (
    <Suspense fallback={<PageSkeleton />}>
      <SchemaView />
    </Suspense>
  );
}
