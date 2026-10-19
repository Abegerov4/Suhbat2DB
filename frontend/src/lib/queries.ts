"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import { api, post } from "./api/client";
import type {
  Datasource,
  Message,
  SchemaSnapshot,
  Session,
  Stats,
  User,
} from "./api/types";

export const keys = {
  me: ["me"] as const,
  datasources: ["datasources"] as const,
  schema: (id: string) => ["datasources", id, "schema"] as const,
  sessions: ["sessions"] as const,
  messages: (id: string) => ["sessions", id, "messages"] as const,
  stats: ["stats"] as const,
};

export const useMe = () =>
  useQuery({
    queryKey: keys.me,
    queryFn: () => api<User>("/auth/me"),
    staleTime: Infinity,
  });

export const useDatasources = () =>
  useQuery({
    queryKey: keys.datasources,
    queryFn: () => api<Datasource[]>("/datasources"),
    // пока идёт индексация — опрос статуса
    refetchInterval: (q) =>
      q.state.data?.some((d) => d.status === "indexing") ? 2000 : false,
  });

export const useSchema = (id: string, enabled = true) =>
  useQuery({
    queryKey: keys.schema(id),
    queryFn: () => api<SchemaSnapshot>(`/datasources/${id}/schema`),
    enabled,
    retry: false,
  });

export const useSessions = () =>
  useQuery({
    queryKey: keys.sessions,
    queryFn: () => api<Session[]>("/sessions"),
  });

export const useMessages = (sessionId: string) =>
  useQuery({
    queryKey: keys.messages(sessionId),
    queryFn: () => api<Message[]>(`/sessions/${sessionId}/messages`),
    staleTime: Infinity, // обновляется вручную после каждого хода
  });

const timezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

export const useStats = (days = 14) =>
  useQuery({
    queryKey: [...keys.stats, days],
    queryFn: () =>
      api<Stats>(
        `/stats?days=${days}&tz=${encodeURIComponent(timezone() || "UTC")}`,
      ),
  });

export function useCreateSession() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (datasource_id: string) =>
      post<Session>("/sessions", { datasource_id }),
    onSuccess: (session) => {
      client.setQueryData<Session[]>(keys.sessions, (old) => [
        session,
        ...(old ?? []),
      ]);
      client.setQueryData<Message[]>(keys.messages(session.id), []);
    },
  });
}

export function useCreateDatasource() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; connection_url: string }) =>
      post<Datasource>("/datasources", body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.datasources }),
  });
}

export function useReindex() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => post<Datasource>(`/datasources/${id}/reindex`),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.datasources }),
  });
}

export function useDeleteDatasource() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api<void>(`/datasources/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.datasources });
      client.invalidateQueries({ queryKey: keys.sessions });
    },
  });
}

export function useFeedback() {
  return useMutation({
    mutationFn: ({
      messageId,
      score,
      comment,
    }: {
      messageId: string;
      score: 1 | -1;
      comment?: string;
    }) => post<void>(`/messages/${messageId}/feedback`, { score, comment }),
  });
}

/** После хода: история, заголовок сессии и сводка на «Обзоре». */
export function refreshAfterTurn(client: QueryClient, sessionId: string) {
  client.invalidateQueries({ queryKey: keys.messages(sessionId) });
  // exact: ключ ["sessions"] — префикс и для истории всех диалогов
  client.invalidateQueries({ queryKey: keys.sessions, exact: true });
  client.invalidateQueries({ queryKey: keys.stats });
}
