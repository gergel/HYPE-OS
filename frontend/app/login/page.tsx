"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
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
      localStorage.setItem("hype_os_token", data.access_token);
      router.push("/dashboard");
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
