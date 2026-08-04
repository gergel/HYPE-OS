"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { setToken } from "@/lib/authFetch";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Csak saját, alkalmazáson belüli útvonalra irányítunk vissza - a "next"
 * paraméter az URL-ből jön, tehát külső címet is bele lehetne írni. */
function biztonsagosCel(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/login")) return "/dashboard";
  return next;
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const body = new URLSearchParams({ username: email, password });
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.detail ?? "Hibás bejelentkezés");
        return;
      }
      const data = await res.json();
      setToken(data.access_token);
      // TELJES oldalbetöltéssel megyünk tovább (nem router.push), mert a
      // kliens-oldali route cache-ben ott maradhat a kiléptetés előtti,
      // "loginra átirányított" változata a céloldalnak - egy sima kliens-
      // oldali navigáció azt játszaná vissza, és úgy tűnne, mintha megint
      // bejelentkezést kérne. Ha volt hova tartott, oda visszük vissza.
      window.location.replace(biztonsagosCel(searchParams.get("next")));
      return;
    } catch {
      setError("Nem sikerült elérni a backend API-t.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6"
      >
        <p className="mb-1 text-lg font-medium text-text-primary">HYPE OS</p>
        <p className="mb-5 text-[13px] text-text-secondary">Jelentkezz be a folytatáshoz</p>

        <label className="mb-3 block">
          <span className="mb-1 block text-[13px] text-text-secondary">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-[var(--radius)] border border-border bg-surface-1 px-3 py-2 text-[13px] text-text-primary outline-none focus:border-text-accent"
          />
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block text-[13px] text-text-secondary">Jelszó</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-[var(--radius)] border border-border bg-surface-1 px-3 py-2 text-[13px] text-text-primary outline-none focus:border-text-accent"
          />
        </label>

        {error && <p className="mb-3 text-[13px] text-text-danger">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-[var(--radius)] bg-bg-accent px-3 py-2 text-[13px] font-medium text-text-accent disabled:opacity-50"
        >
          {loading ? "Belépés..." : "Belépés"}
        </button>
      </form>
    </div>
  );
}
