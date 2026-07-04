"use client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const TOKEN_KEY = "hype_os_token";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24;

/** A tokent localStorage-ba ÉS egy cookie-ba is elmenti - a cookie kell ahhoz,
 * hogy a Next.js middleware és a szerver-oldali (SSR) laprenderelés is lássa,
 * be van-e jelentkezve a felhasználó (a localStorage csak a böngészőben,
 * kliens-oldali kódból érhető el, a middleware/SSR nem látja). */
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
  document.cookie = `${TOKEN_KEY}=${token}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}; samesite=lax`;
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`;
}

/** Kliens-oldali, bejelentkezést igénylő (admin/operátor) írási műveletekhez -
 * a JWT-t a localStorage-ból teszi az Authorization headerbe. Csak "use client"
 * komponensekből hívható (form submit, törlés gomb, stb.) - a szerver-oldali
 * listázó oldalak a cookie-ból olvassák (lásd lib/api.ts apiGet). */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}
