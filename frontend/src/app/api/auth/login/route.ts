import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import {
  backendUrl,
  isHttps,
  jsonError,
  sameOrigin,
  tokenCookie,
  unreachable,
} from "@/lib/server/backend";

/** Вход: токен из ответа бэкенда кладётся в httpOnly-cookie и не отдаётся в браузер. */
export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) {
    return jsonError(403, "forbidden", "Запрос с чужого сайта");
  }
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
    });
  } catch {
    return unreachable();
  }
  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) return NextResponse.json(body, { status: upstream.status });

  const response = new NextResponse(null, { status: 204 });
  response.cookies.set(tokenCookie(body.access_token, isHttps(request)));
  return response;
}
