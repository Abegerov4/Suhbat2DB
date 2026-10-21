"use client";

import { MessageSquarePlus } from "lucide-react";
import Link from "next/link";

import { ActivityChart } from "@/components/dashboard/activity-chart";
import { GettingStarted } from "@/components/dashboard/getting-started";
import { RecentSessions } from "@/components/dashboard/recent-sessions";
import { SourcesCard } from "@/components/dashboard/sources-card";
import { StatCards } from "@/components/dashboard/stat-cards";
import { ValidationSummary } from "@/components/dashboard/validation-summary";
import { SiteHeader } from "@/components/layout/site-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe, useStats } from "@/lib/queries";

export default function OverviewPage() {
  const me = useMe();
  const stats = useStats();
  const name = me.data?.email.split("@")[0];

  return (
    <>
      <SiteHeader
        title={name ? `Добро пожаловать, ${name}` : "Обзор"}
        description="Сводка по вашим диалогам с агентом"
      >
        <Button size="sm" asChild>
          <Link href="/chat" aria-label="Новый диалог">
            <MessageSquarePlus aria-hidden />
            <span className="hidden sm:inline">Новый диалог</span>
          </Link>
        </Button>
      </SiteHeader>

      <div className="flex flex-1 flex-col gap-6 p-4 sm:p-6">
        {stats.isError && (
          <Alert variant="destructive">
            <AlertTitle>Не удалось загрузить сводку</AlertTitle>
            <AlertDescription>{stats.error.message}</AlertDescription>
          </Alert>
        )}
        {stats.data?.questions === 0 && <GettingStarted />}
        <StatCards stats={stats.data} />
        <ActivityChart activity={stats.data?.activity} />
        <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
          {stats.data ? (
            <ValidationSummary stats={stats.data} />
          ) : (
            <Skeleton className="h-80 rounded-xl" />
          )}
          <RecentSessions />
          <div className="lg:col-span-2 xl:col-span-1">
            {stats.data ? (
              <SourcesCard stats={stats.data} />
            ) : (
              <Skeleton className="h-80 rounded-xl" />
            )}
          </div>
        </div>
        <footer className="flex flex-wrap justify-between gap-2 pb-2 text-xs text-muted-foreground">
          <span>Suhbat2DB · Диалоговый анализ реляционных данных</span>
          <span>Каждый SQL проверяется до выполнения</span>
        </footer>
      </div>
    </>
  );
}
