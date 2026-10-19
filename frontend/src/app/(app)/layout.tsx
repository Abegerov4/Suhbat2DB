import type { Metadata } from "next";

import { AppSidebar } from "@/components/layout/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

// шаблон повторяется: строковый title в layout сбрасывает шаблон корня для вложенных страниц
export const metadata: Metadata = {
  title: { default: "Обзор", template: "%s · Suhbat2DB" },
};

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <SidebarProvider>
      <AppSidebar />
      {/* min-w-0: иначе flex-элемент не сжимается уже ширины таблиц внутри */}
      <SidebarInset className="min-w-0">{children}</SidebarInset>
    </SidebarProvider>
  );
}
