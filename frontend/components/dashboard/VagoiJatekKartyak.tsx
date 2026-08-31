"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Gift, Trophy } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import type { VagoiJatekNyertes } from "@/lib/api";

/** A vágói játék GYŐZTESÉNEK ünneplő kártyája (a felhasználó kérése).
 *
 * Hónapváltáskor a rendszer kihirdeti az előző hónap győztesét (lásd backend
 * services/vagoi_jatek.havi_zaras) - a győztes a kihirdetéstől 5 napig ezt a
 * kártyát látja a dashboardja tetején: ő nyert, és ezt nyerte. Csak neki
 * jelenik meg (a summary csak a győztesnek adja vissza az adatot). */
export function VagoiGyoztesKartya({ nyertes }: { nyertes: VagoiJatekNyertes }) {
  return (
    <Link
      href="/vagoi-jatek"
      className="block rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 transition-colors hover:border-text-accent/40"
      style={{
        // Meleg, ünnepi derengés - ugyanaz a homok-tónus, mint a bevétel-widget
        // kiemelt oszlopa, hogy a dashboard színvilágában maradjon.
        backgroundImage: "linear-gradient(120deg, rgba(176,144,111,0.16), transparent 60%)",
      }}
    >
      <div className="flex flex-wrap items-center gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-border bg-surface-2">
          <Trophy className="h-6 w-6" style={{ color: "#cbb187" }} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold text-text-primary">
            Gratulálunk - megnyerted a(z) {nyertes.honap_nev} havi vágói játékot!
          </p>
          <p className="mt-1 text-[13px] text-text-secondary">
            {nyertes.pont} ponttal végeztél az élen.
            {nyertes.nyeremeny
              ? ` Nyereményed: ${nyertes.nyeremeny}.`
              : " A nyereményedről hamarosan értesítünk."}
          </p>
        </div>
        {nyertes.kep_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={nyertes.kep_url}
            alt="A nyeremény"
            className="h-16 w-24 shrink-0 rounded-[var(--radius)] border border-border object-cover"
          />
        )}
      </div>
    </Link>
  );
}

/** ADMIN nyeremény-bekérő: új hónap indult, de a folyó hónap vágói-játék
 * nyereménye még nincs kihirdetve - a verseny addig "tét nélkül" fut. A
 * kártya addig marad a dashboardon, amíg a nyereményt meg nem adják (itt
 * helyben, vagy a Vágói játék oldalon - fotót is ott lehet feltölteni). */
export function VagoiNyeremenyBekero() {
  const router = useRouter();
  const [ertek, setErtek] = useState("");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function mentes() {
    if (!ertek.trim()) return;
    setBusy(true);
    setHiba(null);
    try {
      const ma = new Date();
      const res = await authFetch("/api/v1/vagoi-jatek/nyeremeny", {
        method: "PUT",
        body: JSON.stringify({
          ev: ma.getFullYear(),
          honap: ma.getMonth() + 1,
          nyeremeny: ertek.trim(),
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5">
      <div className="flex flex-wrap items-center gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-border bg-surface-2">
          <Gift className="h-6 w-6 text-text-accent" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold text-text-primary">
            Új hónap indult a vágói játékban - mi lesz a havi nyeremény?
          </p>
          <p className="mt-1 text-[13px] text-text-secondary">
            A verseny akkor megy, ha a hónap elején tudják, miért hajtanak. Írd be a nyereményt, vagy add
            meg (fotóval együtt) a{" "}
            <Link href="/vagoi-jatek" className="text-text-accent hover:underline">
              Vágói játék oldalon
            </Link>
            .
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <input
            value={ertek}
            onChange={(e) => setErtek(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && ertek.trim() && !busy) void mentes();
            }}
            disabled={busy}
            placeholder="pl. egy szabadnap, vacsora…"
            className="min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary focus:outline-none sm:w-56"
          />
          <button
            type="button"
            onClick={mentes}
            disabled={busy || !ertek.trim()}
            className="btn btn-primary !text-[13px]"
          >
            {busy ? "Mentés…" : "Kihirdetés"}
          </button>
        </div>
      </div>
      {hiba && <p className="mt-2 text-[12.5px] text-text-danger">{hiba}</p>}
    </div>
  );
}
