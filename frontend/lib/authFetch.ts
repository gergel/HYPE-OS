"use client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "hype_os_token";

/** Kliens-oldali, bejelentkezést igénylő (admin/operátor) írási műveletekhez -
 * a JWT-t a localStorage-ból teszi az Authorization headerbe. Csak "use client"
 * komponensekből hívható (form submit, törlés gomb, stb.) - a szerver-oldali
 * listázó oldalak továbbra is sima, auth nélküli fetch-csel töltenek be adatot. */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(`${API_BASE_URL}${path}`, { ...init, headers });
}
