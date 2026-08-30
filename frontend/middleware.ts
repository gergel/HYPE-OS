import { NextRequest, NextResponse } from "next/server";
import { resolvePermissionPage } from "@/lib/nav";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_COOKIE = "hype_os_token";
// A cookie ugyanannyi ideig éljen, mint maga a token (backend
// access_token_expire_minutes, 30 nap) - ha a cookie hamarabb tűnne el, a
// felhasználó akkor is kiesne, amikor a munkamenete még érvényes.
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;
// A middleware nem várhat sokáig a backendre: ha lassú, inkább beengedjük a
// felhasználót (a token amúgy is a backendnél dől el minden API-híváskor),
// mint hogy a navigáció beragadjon.
const BACKEND_TIMEOUT_MS = 4000;
// "/p" a Média Portál ÜGYFÉL-oldali nézete (/p/{slug}) - szándékosan publikus,
// mert a valódi ügyfelek, akiknek a linket küldjük, nem HYPE OS alkalmazottak
// (saját, portál-hatókörű jelszó/share-token védi, lásd
// backend/app/api/routes/portal_public.py). "/kerdoiv" az utókövető kérdőív -
// a diszpó-résztvevő crew tagok emailben kapják a linket, ők sem feltétlenül
// HYPE OS felhasználók (lásd backend/app/api/routes/public_utokovetes.py).
// "/adatvedelem" az adatkezelési tájékoztató - a portál fizetési űrlapja és a
// süti-sáv is ide hivatkozik, tehát ugyanazoknak a kijelentkezett ügyfeleknek
// kell elérhetőnek lennie, mint maga a portál.
const PUBLIC_PATHS = ["/login", "/p", "/kerdoiv", "/adatvedelem"];

// A publikus portál SAJÁT domainen fut (hypeclient.com), az admin felület a
// magáén. Ugyanaz a Next.js telepítés szolgálja ki mindkettőt - ezért itt kell
// gondoskodni arról, hogy a portál domainjén NE legyen elérhető a HYPE OS
// belső felülete (se a /login, se egyetlen admin oldal). Enélkül a
// hypeclient.com/projektek is behozná a bejelentkező képernyőt, ami az
// ügyfeleknek szóló domainen zavaró és fölösleges támadási felület.
//
// Beállítás nélkül (NEXT_PUBLIC_PORTAL_HOST üres) minden marad a régiben: egy
// domain, minden útvonal - így a fejlesztői környezet és az egydomaines
// telepítés változtatás nélkül működik.
const PORTAL_HOST = (process.env.NEXT_PUBLIC_PORTAL_HOST ?? "").trim().toLowerCase();
// Amit a portál domainje kiszolgál. Az /adatvedelem azért kell ide, mert a
// portál fizetési űrlapja és a süti-sáv is hivatkozik rá: ugyanazon a
// domainen kell elérhetőnek lennie, ahol a fizetés történik.
const PORTAL_HOST_PATHS = ["/p", "/adatvedelem"];

/** A kérés a portál domainjére érkezett-e. A portot levágjuk (localhost:3000),
 * a "www." előtagot pedig ugyanannak a domainnek tekintjük - aki a
 * www.hypeclient.com/p/... linket kapja, ugyanazt kell lássa. */
function portalDomainrolJon(request: NextRequest): boolean {
  if (PORTAL_HOST === "") return false;
  const host = (request.headers.get("host") ?? "").toLowerCase().split(":")[0];
  return host === PORTAL_HOST || host === `www.${PORTAL_HOST}`;
}

/** A tokenből kiolvassa a lejáratot (exp), ALÁÍRÁS-ELLENŐRZÉS NÉLKÜL - itt csak
 * arról döntünk, kérjünk-e frisset. Az érvényességet mindig a backend mondja
 * meg, a middleware ebből semmilyen jogosultságot nem vezet le. */
function lejaratMasodpercben(token: string): number | null {
  try {
    const payload = JSON.parse(Buffer.from(token.split(".")[1], "base64").toString());
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

/** Kell-e megújítani a tokent: ha az élettartamának már több mint a felén túl
 * van. Így aki használja a rendszert, sosem esik ki, viszont nem is kérünk új
 * tokent minden egyes oldalbetöltésnél. */
function megujitando(token: string): boolean {
  const exp = lejaratMasodpercben(token);
  if (exp === null) return false;
  const hatralevoMasodperc = exp - Date.now() / 1000;
  return hatralevoMasodperc < COOKIE_MAX_AGE_SECONDS / 2;
}

function loginraKuld(request: NextRequest, { tokentTorol }: { tokentTorol: boolean }) {
  const url = new URL("/login", request.url);
  // Megjegyezzük, hova tartott - belépés után oda visz vissza a login oldal,
  // hogy ne a dashboardon kössön ki, és ne kelljen újra odakattintania.
  const cel = request.nextUrl.pathname + request.nextUrl.search;
  if (cel && cel !== "/" && !cel.startsWith("/login")) url.searchParams.set("next", cel);
  const res = NextResponse.redirect(url);
  if (tokentTorol) res.cookies.delete(TOKEN_COOKIE);
  return res;
}

/** Bejelentkezés nélkül semmilyen oldal nem érhető el (kivéve a fenti
 * PUBLIC_PATHS) - és ha a bejelentkezett felhasználóhoz egyénenkénti
 * oldal-korlátozás van beállítva (lásd /api/v1/user-access/me), a nem
 * engedélyezett oldalakat is blokkolja.
 *
 * FONTOS alapelv: aki be van jelentkezve, azt CSAK akkor léptetjük ki, ha a
 * backend kifejezetten azt mondja, hogy a token érvénytelen (401/403). Minden
 * más hiba (a backend épp indul, 502/503-at ad, lassú, hálózati hiba) átmeneti
 * üzemzavar, nem a felhasználó hibája - ilyenkor beengedjük. Korábban bármely
 * nem-200 válasz törölte a munkamenet-cookie-t, ezért egyetlen backend-akadás
 * is kiléptette a felhasználót, és a következő oldalon újra be kellett
 * jelentkeznie. */
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const statikus = pathname.startsWith("/_next") || pathname === "/favicon.ico";

  // A portál domainjén CSAK a portál él. Ami nem oda tartozik, az nem
  // átirányítást kap (az elárulná az admin felület címét), hanem 404-et.
  if (portalDomainrolJon(request) && !statikus) {
    const portalhozTartozik = PORTAL_HOST_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
    if (!portalhozTartozik) {
      return new NextResponse("Nincs ilyen oldal.", {
        status: 404,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }
    return NextResponse.next();
  }

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/")) || statikus) {
    return NextResponse.next();
  }

  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return loginraKuld(request, { tokentTorol: false });
  }

  // NEM a puszta URL első szegmensét nézzük (pl. "/projektek"), hanem a
  // nav.ts-ben definiált, TÉNYLEGES backend jogosultsági kulcsot - enélkül pl.
  // "/projektek/project-kodok" tévesen a "Projektek" jogosultsággal is
  // beengedhető lenne, holott a két oldal külön jogosultság (lásd
  // resolvePermissionPage kommentje).
  // Az /embed/* útvonalak ugyanannak a nézetnek a felugró ablakba szánt,
  // keret nélküli változatai (lásd app/embed/layout.tsx), ezért ugyanaz a
  // jogosultság vonatkozik rájuk - az előtagot le kell vágni, különben a
  // resolvePermissionPage egy nem létező "/embed" oldalt keresne, és a
  // korlátozott hozzáférésű felhasználókat tévesen kizárnánk.
  const permissionPath = pathname.startsWith("/embed/") ? pathname.slice("/embed".length) : pathname;
  const topSegment = resolvePermissionPage(permissionPath);

  let allowedPages: string[] | null = null;
  let anyagKorlat: number[] | null = null;
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/user-access/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
    });
    if (res.status === 401 || res.status === 403) {
      // Csak ez jelenti azt, hogy a munkamenet tényleg lejárt/érvénytelen.
      return loginraKuld(request, { tokentTorol: true });
    }
    if (!res.ok) {
      // Átmeneti backend-hiba (500/502/503/429...): beengedjük, a munkamenetet
      // nem bántjuk. Az oldal saját lekérdezései úgyis jelzik, ha nincs adat.
      return NextResponse.next();
    }
    const hozzaferes = (await res.json()) as {
      allowed_pages: string[] | null;
      lathato_deliverable_idk: number[] | null;
    };
    allowedPages = hozzaferes.allowed_pages;
    anyagKorlat = hozzaferes.lathato_deliverable_idk;
  } catch {
    // Időtúllépés vagy hálózati hiba - ugyanaz a szabály: nem léptetjük ki.
    return NextResponse.next();
  }

  // KORLÁTOZOTT fiók (külsős vágó): a rábízott anyagon kívül semmit nem
  // nyithat meg. Számára a Dashboard a teendő-listája, az anyag pedig felugró
  // ablakban (az /embed változaton) nyílik - minden más útvonal a
  // Dashboardra visz vissza. A tényleges adat-hozzáférést a backend tartja be
  // (lásd core/security.lathato_anyagok), ez a felület-szintű zár.
  if (anyagKorlat !== null) {
    const anyagEgyezes = permissionPath.match(/^\/utomunka\/(\d+)/);
    const sajatAnyag = anyagEgyezes !== null && anyagKorlat.includes(Number(anyagEgyezes[1]));
    if (topSegment !== "/dashboard" && !sajatAnyag) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
  } else if (
    allowedPages &&
    allowedPages.length > 0 &&
    topSegment !== "/dashboard" &&
    // A "nincs jogosultság" oldal saját magát muszáj kivennie a zár alól -
    // különben pont az irányítaná ide magát végtelen körben.
    topSegment !== "/nincs-jogosultsag" &&
    // Az aliaszolt oldalak (pl. a Diszpó jogából nyíló Projektek és
    // Felszerelés) is BENNE VANNAK az allowed_pages-ben - a szerver számolja
    // bele, lásd backend core/security.elerheto_oldalak. Így a menü és ez a
    // zár ugyanabból az egy listából dolgozik, nem tud elcsúszni.
    !allowedPages.includes(topSegment)
  ) {
    // "Nincs jogosultság" oldal, NEM csendben a Dashboard - így aki egy
    // olyan linkre kattint, amihez nincs joga, kap egy magyarázatot ahelyett,
    // hogy azt hinné, a link egyszerűen nem működik (lásd
    // app/(app)/nincs-jogosultsag/page.tsx - onnan a böngésző-előzmény
    // "Vissza" gombjával pontosan oda tud visszalépni, ahonnan jött).
    return NextResponse.redirect(new URL("/nincs-jogosultsag", request.url));
  }

  const response = NextResponse.next();

  // GÖRDÜLŐ munkamenet: ha a token már a lejárata felén túl van, kérünk egy
  // frisset, és azt tesszük vissza a cookie-ba. Aki használja a rendszert,
  // ezért sosem esik ki - nem kell 30 naponta újra bejelentkeznie sem.
  if (megujitando(token)) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
        signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      });
      if (res.ok) {
        const { access_token } = (await res.json()) as { access_token: string };
        response.cookies.set(TOKEN_COOKIE, access_token, {
          path: "/",
          maxAge: COOKIE_MAX_AGE_SECONDS,
          sameSite: "lax",
        });
      }
    } catch {
      // A megújítás legfeljebb a következő oldalbetöltéskor sikerül - a
      // meglévő token addig is érvényes, tehát ebből nem lehet kiléptetés.
    }
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
