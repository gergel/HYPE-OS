"use client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const TOKEN_KEY = "hype_os_token";
// Ugyanaz, mint a backend access_token_expire_minutes (30 nap) és a
// middleware COOKIE_MAX_AGE_SECONDS - ha a cookie hamarabb járna le, mint a
// token, a felhasználó akkor is kiesne, amikor a munkamenete még érvényes.
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

/** A token EGYETLEN forrása a cookie - a middleware és a szerver-oldali (SSR)
 * laprenderelés is ezt olvassa (lásd lib/api.ts), és a gördülő munkamenet is
 * ezt írja felül, amikor megújítja a tokent. A kliens-oldali hívások ezért
 * szintén innen veszik: ha a localStorage-ból olvasnánk, a megújítás után ott
 * a RÉGI token maradna, és a mentések elkezdenének 401-gyel elszállni,
 * miközben az oldalak betöltése még működik. */
export function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const cookie = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${TOKEN_KEY}=`))
    ?.slice(TOKEN_KEY.length + 1);
  if (cookie) return cookie;
  // Régi munkamenetek: korábban a localStorage volt az elsődleges tároló. Ha
  // csak ott van token, átemeljük a cookie-ba, hogy a middleware is lássa.
  const legacy = localStorage.getItem(TOKEN_KEY);
  if (legacy) {
    setToken(legacy);
    return legacy;
  }
  return null;
}

/** A tokent a cookie-ba menti - a middleware/SSR csak ezt látja, a
 * localStorage-ot nem. A localStorage-ba is beírjuk, hogy a még nyitva lévő,
 * régebbi kódot futtató fülek se essenek szét. */
export function setToken(token: string) {
  document.cookie = `${TOKEN_KEY}=${token}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}; samesite=lax`;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`;
}

/** Kliens-oldali, bejelentkezést igénylő (admin/operátor) írási műveletekhez -
 * a JWT-t a cookie-ból teszi az Authorization headerbe. Csak "use client"
 * komponensekből hívható (form submit, törlés gomb, stb.) - a szerver-oldali
 * listázó oldalak ugyanezt a cookie-t olvassák (lásd lib/api.ts apiGet). */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  // FormData-nál a böngészőnek KELL magának beállítania a Content-Type-ot (a
  // multipart boundary miatt) - ha itt application/json-t kényszerítenénk rá,
  // a fájlfeltöltés végpontok nem tudnák szétszedni a body-t.
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}
