import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Quick first check: no session cookie at all means "not signed in", so go to
// /login. The real check (is the cookie valid?) happens on the server in
// src/app/(app)/layout.tsx and in every backend endpoint.
export function proxy(request: NextRequest) {
  if (!request.cookies.has("casio_session")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  // Every app section (keep in sync with src/lib/nav.ts).
  matcher: [
    "/overview/:path*",
    "/transactions/:path*",
    "/import/:path*",
    "/rules/:path*",
    "/budgets/:path*",
    "/subscriptions/:path*",
    "/profile/:path*",
    "/money-model/:path*",
    "/goals/:path*",
    "/what-if/:path*",
    "/reports/:path*",
    "/coach/:path*",
    "/settings/:path*",
  ],
};
