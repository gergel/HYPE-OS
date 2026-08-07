"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import type { ContractPeriod } from "@/lib/api";

/** Egy keretszerződés ÉRVÉNYESSÉGE: be van-e kapcsolva, és mettől meddig élt.
 *
 * Nem elég egy kezdet/vég dátumpár: egy emberrel nem feltétlenül folyamatos a
 * viszony - van egy időszakra, aztán fél évig nincs, majd újra kötünk vele
 * egyet. Ezért tetszőleges számú időszak vehető fel egymás után.
 *
 * A tétje: a keretszerződés csak akkor váltja ki a projektenkénti eseti
 * szerződést, ha a FORGATÁS NAPJÁN élt - a szünetbe eső projektekhez az
 * utókövetés eseti szerződést fog kérni (lásd backend models/contract.py
 * keretszerzodes_ervenyes). */
export function KeretszerzodesErvenyesseg({
  contractId,
  aktiv,
  idoszakok,
  canEdit,
}: {
  contractId: number;
  aktiv: boolean;
  idoszakok: ContractPeriod[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [nyitva, setNyitva] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ujKezdet, setUjKezdet] = useState("");
  const [ujVeg, setUjVeg] = useState("");
  // A kapcsoló AZONNAL váltson, ne csak a szerver válasza után: a mentés
  // eredményét a router.refresh() hozza vissza, ami eltart pár tizedmásodpercig
  // - addig a pipa "beragadtnak" tűnne. Hiba esetén visszaáll.
  const [aktivAllapot, setAktivAllapot] = useState(aktiv);
  const [elozoAktiv, setElozoAktiv] = useState(aktiv);
  if (elozoAktiv !== aktiv) {
    setElozoAktiv(aktiv);
    setAktivAllapot(aktiv);
  }

  async function kuld(url: string, method: string, body?: unknown) {
    setBusy(true);
    try {
      const res = await authFetch(url, {
        method,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return false;
      }
      router.refresh();
      return true;
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function aktivValt() {
    const cel = !aktivAllapot;
    setAktivAllapot(cel);
    const ok = await kuld(`/api/v1/contracts/${contractId}`, "PATCH", { aktiv: cel });
    if (!ok) setAktivAllapot(!cel);
  }

  async function idoszakHozzad() {
    const ok = await kuld(`/api/v1/contracts/${contractId}/idoszakok`, "POST", {
      kezdet: ujKezdet || null,
      veg: ujVeg || null,
    });
    if (ok) {
      setUjKezdet("");
      setUjVeg("");
    }
  }

  // A sorba csak az első néhány fér el olvashatóan - a többit szám jelzi, a
  // teljes lista a lenyitott panelen van.
  const OSSZEFOGLALO_DB = 2;
  const felsorolt = idoszakok
    .slice(0, OSSZEFOGLALO_DB)
    .map((i) => `${i.kezdet ?? "…"} – ${i.veg ?? "ma is"}`)
    .join(", ");
  const maradek = idoszakok.length - OSSZEFOGLALO_DB;
  const osszefoglalo =
    idoszakok.length === 0 ? "időbeli korlát nélkül" : maradek > 0 ? `${felsorolt} +${maradek}` : felsorolt;

  return (
    <span className="inline-flex flex-col items-start gap-1">
      <span className="flex items-center gap-2">
        <label className="flex cursor-pointer items-center gap-1.5 text-[12.5px] text-text-secondary">
          <input
            type="checkbox"
            checked={aktivAllapot}
            disabled={!canEdit || busy}
            onChange={aktivValt}
            className="cursor-pointer"
          />
          {aktivAllapot ? "Aktív" : "Nem aktív"}
        </label>
        <button
          type="button"
          onClick={() => setNyitva((o) => !o)}
          className="text-[12px] text-text-secondary hover:text-text-primary hover:underline"
        >
          {idoszakok.length === 0 ? "Időszakok" : `Időszakok (${idoszakok.length})`}
        </button>
      </span>
      {!nyitva && <span className="text-[11.5px] text-text-muted">{osszefoglalo}</span>}

      {nyitva && (
        <span className="mt-1 flex w-full flex-col gap-1.5 rounded-[var(--radius)] border border-border bg-surface-3 p-2">
          <span className="text-[11.5px] text-text-muted">
            Csak akkor váltja ki az eseti szerződést, ha a forgatás napján élt. Több időszak is felvehető (pl. volt,
            szünetelt, majd újra). Üres &quot;meddig&quot; = azóta is él.
          </span>
          {idoszakok.map((i) => (
            <span key={i.id} className="flex items-center gap-2 text-[12.5px] text-text-primary">
              <span>
                {i.kezdet ?? "kezdetektől"} – {i.veg ?? "ma is"}
              </span>
              {canEdit && (
                <button
                  type="button"
                  disabled={busy}
                  aria-label="Időszak törlése"
                  onClick={() => kuld(`/api/v1/contracts/idoszakok/${i.id}`, "DELETE")}
                  className="text-text-secondary hover:text-text-danger disabled:opacity-40"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </span>
          ))}
          {idoszakok.length === 0 && (
            <span className="text-[12.5px] text-text-muted">Nincs időszak – időbeli korlát nélkül érvényes.</span>
          )}
          {canEdit && (
            <span className="flex flex-wrap items-center gap-1.5">
              <input
                type="date"
                value={ujKezdet}
                onChange={(e) => setUjKezdet(e.target.value)}
                aria-label="Időszak kezdete"
                className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12.5px] text-text-primary"
              />
              <span className="text-[12.5px] text-text-muted">–</span>
              <input
                type="date"
                value={ujVeg}
                onChange={(e) => setUjVeg(e.target.value)}
                aria-label="Időszak vége"
                className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12.5px] text-text-primary"
              />
              <button
                type="button"
                disabled={busy || (!ujKezdet && !ujVeg)}
                onClick={idoszakHozzad}
                className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-2 disabled:opacity-40"
              >
                + Időszak
              </button>
            </span>
          )}
        </span>
      )}
    </span>
  );
}
