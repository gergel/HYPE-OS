"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { clearToken } from "@/lib/authFetch";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type CurrentUser = {
  id: number;
  full_name: string;
  email: string | null;
  role: string;
  is_active: boolean;
};

export function AccountCard() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null | undefined>(undefined);

  useEffect(() => {
    const token = localStorage.getItem("hype_os_token");
    if (!token) {
      setUser(null);
      return;
    }
    fetch(`${API_BASE_URL}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => (res.ok ? res.json() : null))
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  function handleLogout() {
    clearToken();
    router.push("/login");
    router.refresh();
  }

  return (
    <Card title="Fiókom">
      {user === undefined && <p className="text-[13px] text-text-muted">Betöltés…</p>}
      {user === null && (
        <p className="text-[13px] text-text-secondary">
          Nem vagy bejelentkezve.{" "}
          <a href="/login" className="text-text-accent hover:underline">
            Bejelentkezés
          </a>
        </p>
      )}
      {user && (
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[13px] text-text-primary">{user.full_name}</p>
            <p className="text-[12px] text-text-muted">{user.email ?? "–"}</p>
            <div className="mt-2 flex gap-2">
              <StatusBadge label={user.role} tone="neutral" />
              <StatusBadge label={user.is_active ? "Aktív" : "Inaktív"} tone={user.is_active ? "success" : "neutral"} />
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Kijelentkezés
          </button>
        </div>
      )}
    </Card>
  );
}
