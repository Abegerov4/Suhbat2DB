import { Skeleton } from "@/components/ui/skeleton";

/** Статическая оболочка страницы, пока данные из URL не доступны. */
export function PageSkeleton() {
  return (
    <div className="flex flex-1 flex-col" aria-busy="true">
      <div className="flex h-14 items-center gap-3 border-b px-4 sm:px-6">
        <Skeleton className="size-7" />
        <Skeleton className="h-4 w-48" />
      </div>
      <div className="flex flex-col gap-4 p-4 sm:p-6">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    </div>
  );
}
