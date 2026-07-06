"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { Lock } from "lucide-react";
import { Button } from "@/components/media-portal/ui/button";
import { unlockProject } from "@/lib/portalApi";

export function PasswordGate({
  slug,
  title,
  cover,
  onUnlock,
}: {
  slug: string;
  title?: string;
  cover?: string;
  onUnlock: (token: string) => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError("");
    try {
      const { token } = await unlockProject(slug, password);
      sessionStorage.setItem(`hype_unlock_${slug}`, token);
      onUnlock(token);
    } catch {
      setError("Hibás jelszó, próbáld újra.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center px-6">
      {cover && (
        <div className="absolute inset-0 overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={cover} alt="" className="h-full w-full object-cover opacity-25 blur-sm" />
          <div className="absolute inset-0 bg-ink/80" />
        </div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative w-full max-w-sm rounded-3xl border border-ink-line bg-ink-card/80 p-8 backdrop-blur-xl"
      >
        <span className="mb-5 flex h-12 w-12 items-center justify-center rounded-full border border-ink-line text-ember">
          <Lock className="h-5 w-5" />
        </span>
        <p className="font-mono text-xs uppercase tracking-eyebrow text-mist">Védett projekt</p>
        <h1 className="mt-2 font-display text-2xl text-bone">{title || "Add meg a jelszót"}</h1>
        <p className="mt-2 text-sm text-mist">Ez a portál privát. Add meg a meghívóban kapott jelszót.</p>

        <input
          type="password"
          value={password}
          autoFocus
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Jelszó"
          className="mt-6 w-full rounded-full border border-ink-line bg-ink px-5 py-3 text-bone outline-none transition focus:border-ember/60"
        />
        {error && <p className="mt-3 text-sm text-ember">{error}</p>}

        <Button variant="ember" size="lg" className="mt-5 w-full" disabled={loading || !password} onClick={submit}>
          {loading ? "Feloldás…" : "Portál feloldása"}
        </Button>
      </motion.div>
    </main>
  );
}
