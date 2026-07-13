import { NextRequest, NextResponse } from "next/server";
import { resolvePermissionPage } from "@/lib/nav";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_COOKIE = "hype_os_token";
// "/p" a Média Portál ÜGYFÉL-oldali nézete (/p/{slug}) - szándékosan publikus,
// mert a valódi ügyfelek, akiknek a linket küldjük, nem HYPE OS alkalmazottak
// (saját, portál-hatókörű jelszó/share-token védi, lásd
// backend/app/api/routes/portal_public.py). "/kerdoiv" az utókövető kérdőív -
// a diszpó-résztvevő crew tagok emailben kapják a linket, ők sem feltétlenül
// HYPE OS felhasználók (lásd backend/app/api/routes/public_utokovetes.py).
const PUBLIC_PATHS = ["/login", "/p", "/kerdoiv"];

/** Bejelentkezés nélkül semmilyen oldal nem érhető el (kivéve a fenti
 * PUBLIC_PATHS) - és ha a bejelentkezett felhasználóhoz egyénenkénti
 * oldal-korlátozás van beállítva (lásd /api/v1/user-access/me), a nem
 * engedélyezett oldalakat is blokkolja. */
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

  // NEM a puszta URL első szegmensét nézzük (pl. "/projektek"), hanem a
  // nav.ts-ben definiált, TÉNYLEGES backend jogosultsági kulcsot - enélkül pl.
  // "/projektek/project-kodok" tévesen a "Projektek" jogosultsággal is
  // beengedhető lenne, holott a két oldal külön jogosultság (lásd
  // resolvePermissionPage kommentje).
  const topSegment = resolvePermissionPage(pathname);

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
