/**
 * Прокси `/api/*` → FastAPI `/api/*` с JWT из httpOnly-cookie.
 * Тело ответа передаётся потоком, поэтому SSE агента идёт без буферизации,
 * а обрыв соединения браузером (кнопка «Остановить») обрывает и запрос к бэкенду.
 */
import type { NextRequest } from "next/server";

import {
  backendUrl,
  jsonError,
  sameOrigin,
  TOKEN_COOKIE,
  unreachable,
} from "@/lib/server/backend";

const FORWARD_REQUEST = ["content-type", "accept", "x-request-id"];
const FORWARD_RESPONSE = [
  "content-type",
  "cache-control",
  "x-request-id",
  "x-accel-buffering",
];

async function forward(
  request: NextRequest,
  ctx: RouteContext<"/api/[...path]">,
) {
  if (!sameOrigin(request)) {
    return jsonError(403, "forbidden", "Запрос с чужого сайта");
  }
  const { path } = await ctx.params;
  const url = `${backendUrl()}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (token) headers.set("authorization", `Bearer ${token}`);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      signal: request.signal,
      cache: "no-store",
      redirect: "manual",
    });
  } catch (e) {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    console.error("backend proxy failed", url, e);
    return unreachable();
  }

  const responseHeaders = new Headers();
  for (const name of FORWARD_RESPONSE) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  if (upstream.headers.get("content-type")?.startsWith("text/event-stream")) {
    responseHeaders.set("cache-control", "no-cache, no-transform");
    responseHeaders.set("x-accel-buffering", "no");
  }
  const empty = upstream.status === 204 || upstream.status === 304;
  return new Response(empty ? null : upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export {
  forward as GET,
  forward as POST,
  forward as PUT,
  forward as PATCH,
  forward as DELETE,
};
