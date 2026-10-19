/**
 * Клиент REST API. Запросы идут на тот же origin (`/api/*`), а route handler
 * Next.js пересылает их бэкенду и подставляет JWT из httpOnly-cookie.
 */
import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const NETWORK_MESSAGE = "Сервер недоступен. Проверьте, что backend запущен.";

export async function toApiError(response: Response): Promise<ApiError> {
  let body: Partial<ApiErrorBody> = {};
  try {
    body = await response.json();
  } catch {
    // тело не JSON (например, 502 от прокси)
  }
  const error = body.error;
  return new ApiError(
    response.status,
    error?.code ?? "http_error",
    error?.message ?? `Ошибка ${response.status}`,
  );
}

/** Сессия истекла: на страницу входа с возвратом туда, где был пользователь. */
export function redirectToLogin() {
  if (typeof window === "undefined") return;
  const next = window.location.pathname + window.location.search;
  // полная перезагрузка намеренно: сбрасывает кэш запросов и состояние потока
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(next)}`);
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "network_error", NETWORK_MESSAGE);
  }
  if (response.status === 401 && !path.startsWith("/auth/")) {
    redirectToLogin();
  }
  if (!response.ok) throw await toApiError(response);
  return response;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(path, init);
  if (response.status === 204 || response.status === 202) {
    const text = await response.text();
    return (text ? JSON.parse(text) : undefined) as T;
  }
  return (await response.json()) as T;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
