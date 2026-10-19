/**
 * Связь с FastAPI (Backend for Frontend). Только для серверного кода:
 * JWT живёт в httpOnly-cookie и недоступен JavaScript в браузере (защита от XSS).
 */
import "server-only";

export const TOKEN_COOKIE = "s2d_token";

/** Адрес бэкенда читается при каждом запросе: в Docker задаётся в рантайме. */
export const backendUrl = () =>
  (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Совпадает с JWT_TTL_MINUTES бэкенда (24 ч): cookie не переживает токен. */
const MAX_AGE = 60 * 60 * 24;

export function tokenCookie(token: string, secure: boolean) {
  return {
    name: TOKEN_COOKIE,
    value: token,
    httpOnly: true,
    sameSite: "lax" as const, // cookie не уходит с POST с чужих сайтов (CSRF)
    secure,
    path: "/",
    maxAge: MAX_AGE,
  };
}

export const isHttps = (request: Request) =>
  new URL(request.url).protocol === "https:" ||
  request.headers.get("x-forwarded-proto") === "https";

/**
 * Изменяющие запросы принимаются только со своего origin. SameSite=Lax уже
 * закрывает CSRF в современных браузерах; проверка Origin — второй рубеж.
 */
export function sameOrigin(request: Request): boolean {
  if (["GET", "HEAD", "OPTIONS"].includes(request.method)) return true;
  const origin = request.headers.get("origin");
  if (!origin) return true; // не браузерный клиент: cookie он не несёт
  const host =
    request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export const jsonError = (status: number, code: string, message: string) =>
  Response.json({ error: { code, message } }, { status });

export const unreachable = () =>
  jsonError(502, "backend_unreachable", "Backend недоступен");
