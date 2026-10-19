/**
 * Оптимистичная проверка входа: без cookie — на /login. Подлинность токена
 * проверяет бэкенд; при 401 клиент сам отправляет на страницу входа.
 */
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const TOKEN_COOKIE = "s2d_token";
const PUBLIC = ["/login", "/register"];

export function proxy(request: NextRequest) {
  // Предзагрузка ссылок получает статическую оболочку без данных (данные — только
  // через API с cookie), поэтому её не перенаправляем: иначе 404 на чужом сегменте.
  if (
    request.headers.has("next-router-prefetch") ||
    request.headers.has("next-router-segment-prefetch")
  ) {
    return NextResponse.next();
  }
  const { pathname, search } = request.nextUrl;
  const authenticated = request.cookies.has(TOKEN_COOKIE);
  const isPublic = PUBLIC.includes(pathname);

  if (!authenticated && !isPublic) {
    const url = new URL("/login", request.url);
    if (pathname !== "/") url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  if (authenticated && isPublic) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // API, статика и файлы с расширением не проверяются
  matcher: ["/((?!api|_next/static|_next/image|.*\\..*).*)"],
};
