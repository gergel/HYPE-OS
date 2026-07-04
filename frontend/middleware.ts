import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_COOKIE = "hype_os_token";
const PUBLIC_PATHS = ["/login"];

/** Bejelentkezés nélkül semmilyen oldal nem érhető el (kivéve /login) - és ha
 * a bejelentkezett felhasználóhoz egyénenkénti oldal-korlátozás van beállítva
 * (lásd /api/v1/user-access/me), a nem engedélyezett oldalakat is blokkolja. */
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (
    PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/")) ||
    pathname.startsWith("/_next") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  const topSegment = "/" + (pathname.split("/").filter(Boolean)[0] ?? "");

  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/user-access/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) {
      const redirectRes = NextResponse.redirect(new URL("/login", request.url));
      redirectRes.cookies.delete(TOKEN_COOKIE);
      return redirectRes;
    }
    const data: { allowed_pages: string[] | null } = await res.json();
    if (data.allowed_pages && data.allowed_pages.length > 0 && topSegment !== "/dashboard") {
      if (!data.allowed_pages.includes(topSegment)) {
        return NextResponse.redirect(new URL("/dashboard", request.url));
      }
    }
  } catch {
    // Ha a backend pillanatnyilag nem érhető el, nem zárjuk ki a felhasználót emiatt -
    // az oldal saját szerver-oldali lekérdezései úgyis hibát fognak jelezni.
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
