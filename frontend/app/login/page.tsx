"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
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
  // Jelszó-megjelenítés kapcsoló (a felhasználó kérése): a szemecske ikonnal
  // ellenőrizhető, mit gépelt be az ember.
  const [jelszoLatszik, setJelszoLatszik] = useState(false);

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
    <div className="flex flex-1 items-center justify-center p-8">
      <form
        onSubmit={handleSubmit}
        className="fade-in w-full max-w-[380px] rounded-[var(--radius-xl)] border border-border bg-surface-2 p-8"
      >
        <p className="mb-1.5 text-[19px] font-semibold tracking-[-0.02em] text-text-primary">HYPE OS</p>
        <p className="mb-7 text-[13px] text-text-muted">Jelentkezz be a folytatáshoz</p>

        <label className="mb-4 block">
          <span className="mb-1.5 block text-[13px] text-text-secondary">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="field w-full"
          />
        </label>

        <label className="mb-6 block">
          <span className="mb-1.5 block text-[13px] text-text-secondary">Jelszó</span>
          <div className="relative">
            <input
              type={jelszoLatszik ? "text" : "password"}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="field w-full pr-10"
            />
            <button
              type="button"
              onClick={() => setJelszoLatszik((v) => !v)}
              aria-label={jelszoLatszik ? "Jelszó elrejtése" : "Jelszó megjelenítése"}
              tabIndex={-1}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-text-muted hover:text-text-primary"
            >
              {jelszoLatszik ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </label>

        {error && <p className="mb-3 text-[13px] text-text-danger">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="btn btn-primary w-full !py-2.5"
        >
          {loading ? "Belépés..." : "Belépés"}
        </button>
      </form>
    </div>
  );
}
