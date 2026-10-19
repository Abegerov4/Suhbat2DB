"use client";

import {
  Database,
  LayoutDashboard,
  MessageSquare,
  MessageSquarePlus,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { useSessions } from "@/lib/queries";

import { Logo } from "./logo";
import { NavUser } from "./nav-user";

const NAV = [
  { href: "/", label: "Обзор", icon: LayoutDashboard },
  { href: "/chat", label: "Новый диалог", icon: MessageSquarePlus },
  { href: "/datasources", label: "Источники данных", icon: Database },
];

/** Подсветка активного пункта зависит от URL, поэтому меню рендерится внутри Suspense. */
function CurrentPath({
  children,
}: {
  children: (pathname: string | null) => React.ReactNode;
}) {
  return children(usePathname());
}

export function AppSidebar() {
  const { setOpenMobile } = useSidebar();
  const close = () => setOpenMobile(false);
  const menus = (pathname: string | null) => (
    <>
      <NavMain pathname={pathname} onNavigate={close} />
      <NavSessions pathname={pathname} onNavigate={close} />
    </>
  );

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/" onClick={close}>
                <Logo />
                <span className="grid flex-1 text-left leading-tight">
                  <span className="truncate font-semibold">Suhbat2DB</span>
                  <span className="truncate text-xs text-muted-foreground">
                    Диалоговый анализ данных
                  </span>
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <Suspense fallback={menus(null)}>
          <CurrentPath>{menus}</CurrentPath>
        </Suspense>
      </SidebarContent>

      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

function NavMain({
  pathname,
  onNavigate,
}: {
  pathname: string | null;
  onNavigate: () => void;
}) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Навигация</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {NAV.map((item) => {
            const active =
              item.href === "/" || item.href === "/chat"
                ? pathname === item.href
                : Boolean(pathname?.startsWith(item.href));
            return (
              <SidebarMenuItem key={item.href}>
                <SidebarMenuButton
                  asChild
                  isActive={active}
                  tooltip={item.label}
                >
                  <Link href={item.href} onClick={onNavigate}>
                    <item.icon aria-hidden />
                    <span>{item.label}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

function NavSessions({
  pathname,
  onNavigate,
}: {
  pathname: string | null;
  onNavigate: () => void;
}) {
  const sessions = useSessions();
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>Диалоги</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {sessions.isPending &&
            Array.from({ length: 4 }, (_, i) => (
              <SidebarMenuItem key={i}>
                <SidebarMenuSkeleton />
              </SidebarMenuItem>
            ))}
          {sessions.data?.length === 0 && (
            <li className="px-2 py-1.5 text-xs text-muted-foreground">
              Пока нет диалогов
            </li>
          )}
          {sessions.data?.slice(0, 30).map((session) => {
            const href = `/chat/${session.id}`;
            return (
              <SidebarMenuItem key={session.id}>
                <SidebarMenuButton asChild isActive={pathname === href}>
                  <Link href={href} onClick={onNavigate} title={session.title}>
                    <MessageSquare aria-hidden />
                    <span>{session.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
