"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";
import { ModalReteg } from "@/components/ModalReteg";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";

/** VINYÓK KEZELÉSE (a felhasználó kérése): új vinyó név felvétele, átnevezés
 * és törlés - felugró ablakban, az Utómunka "Vinyók szerint" kártyájáról.
 *
 * KÜLÖN jogosultsághoz kötött: admin mindig kezelheti, más csak akkor, ha
 * admin megadta neki (lásd backend postproduction._vinyo_kezelheto) - a gomb
 * ezért csak annak látszik, akinél a vinyo-options válasz kezelheto=true.
 * Az átnevezés/törlés az ÖSSZES anyag vinyó-listáján átfut, nem csak a
 * választható opciókon. */
export function VinyoKezeles({ kezdetiOpciok, isAdmin, emberek }: {
  kezdetiOpciok: string[];
  /** Admin látja a jogosultság-kiosztást is (ki kezelheti a vinyókat). */
  isAdmin: boolean;
  emberek: { id: number; nev: string }[];
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitva, setNyitva] = useState(false);
  const [opciok, setOpciok] = useState(kezdetiOpciok);
  const [ujNev, setUjNev] = useState("");
  const [atnevezes, setAtnevezes] = useState<{ regi: string; uj: string } | null>(null);
  const [busy, setBusy] = useState(false);
  // Kik kezelhetik a vinyókat az adminon kívül - csak adminnak töltjük be.
  const [kezelok, setKezelok] = useState<number[] | null>(null);

  useEffect(() => {
    if (!nyitva || !isAdmin || kezelok !== null) return;
    authFetch("/api/v1/deliverables/vinyo-kezelok")
      .then((res) => (res.ok ? res.json() : null))
      .then((adat: { employee_ids: number[] } | null) => adat && setKezelok(adat.employee_ids))
      .catch(() => {});
  }, [nyitva, isAdmin, kezelok]);

  async function hivas(ut: string, torzs: unknown): Promise<boolean> {
    setBusy(true);
    try {
      const res = await authFetch(ut, { method: "POST", body: JSON.stringify(torzs) });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        alert(`Sikertelen: ${adat?.detail ?? res.status}`);
        return false;
      }
      if (Array.isArray(adat?.options)) setOpciok(adat.options);
      router.refresh();
      return true;
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function ujVinyo() {
    if (!ujNev.trim()) return;
    if (await hivas("/api/v1/deliverables/vinyo-nevek", { nev: ujNev.trim() })) setUjNev("");
  }

  async function atnevez() {
    if (!atnevezes || !atnevezes.uj.trim()) return;
    if (await hivas("/api/v1/deliverables/vinyo-nevek/atnevezes", { regi: atnevezes.regi, uj: atnevezes.uj.trim() })) {
      setAtnevezes(null);
    }
  }

  async function torol(nev: string) {
    if (
      !(await confirm(
        `Törlöd a(z) "${nev}" vinyót? A név az összes anyagról is lekerül - maguk az anyagok megmaradnak.`,
      ))
    ) {
      return;
    }
    await hivas("/api/v1/deliverables/vinyo-nevek/torles", { nev });
  }

  async function kezeloValt(employeeId: number) {
    if (kezelok === null) return;
    const kovetkezo = kezelok.includes(employeeId)
      ? kezelok.filter((i) => i !== employeeId)
      : [...kezelok, employeeId];
    setKezelok(kovetkezo);
    try {
      const res = await authFetch("/api/v1/deliverables/vinyo-kezelok", {
        method: "PUT",
        body: JSON.stringify({ employee_ids: kovetkezo }),
      });
      if (!res.ok) {
        const adat = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${adat?.detail ?? res.status}`);
        setKezelok(kezelok);
      }
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
      setKezelok(kezelok);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className="rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
      >
        Vinyók kezelése
      </button>

      {nyitva && (
        <ModalReteg onClose={busy ? undefined : () => setNyitva(false)}>
          <div
            className="my-auto flex max-h-[86vh] w-full max-w-lg flex-col rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">Vinyók kezelése</h3>
            <p className="mb-4 text-[12px] text-text-muted">
              Átnevezésnél és törlésnél a név az összes anyag vinyó-listájában is átíródik/lekerül.
            </p>

            <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
              {opciok.map((nev) => (
                <div key={nev} className="flex items-center gap-2 rounded-[var(--radius)] bg-surface-3 px-2.5 py-1.5">
                  {atnevezes?.regi === nev ? (
                    <>
                      <input
                        autoFocus
                        value={atnevezes.uj}
                        onChange={(e) => setAtnevezes({ regi: nev, uj: e.target.value })}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void atnevez();
                          if (e.key === "Escape") setAtnevezes(null);
                        }}
                        className="w-full flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
                      />
                      <button
                        type="button"
                        disabled={busy || !atnevezes.uj.trim()}
                        onClick={() => void atnevez()}
                        className="shrink-0 text-[12.5px] text-text-accent hover:underline disabled:opacity-50"
                      >
                        Mentés
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => setAtnevezes(null)}
                        className="shrink-0 text-[12.5px] text-text-muted hover:text-text-secondary"
                      >
                        Mégse
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="flex-1 text-[13px] text-text-primary [overflow-wrap:anywhere]">{nev}</span>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => setAtnevezes({ regi: nev, uj: nev })}
                        title="Átnevezés"
                        className="shrink-0 p-1 text-text-muted hover:text-text-secondary disabled:opacity-50"
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void torol(nev)}
                        title="Vinyó törlése"
                        className="shrink-0 p-1 text-text-muted hover:text-text-danger disabled:opacity-50"
                      >
                        <Trash2 size={13} />
                      </button>
                    </>
                  )}
                </div>
              ))}
              {opciok.length === 0 && <p className="text-[13px] text-text-muted">Még nincs egyetlen vinyó sem.</p>}
            </div>

            <div className="mt-3 flex gap-2 border-t border-border pt-3">
              <input
                value={ujNev}
                onChange={(e) => setUjNev(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && void ujVinyo()}
                placeholder="Új vinyó neve…"
                className="w-full flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
              />
              <button
                type="button"
                disabled={busy || !ujNev.trim()}
                onClick={() => void ujVinyo()}
                className="shrink-0 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                + Hozzáadás
              </button>
            </div>

            {/* A JOGOSULTSÁG kiosztása (a felhasználó kérése: adminból lehessen
                megadni, ki kezelheti a vinyókat) - csak admin látja. */}
            {isAdmin && (
              <div className="mt-4 border-t border-border pt-3">
                <p className="mb-1.5 text-[13px] text-text-primary">Rajtad (adminokon) kívül kezelheti:</p>
                {kezelok === null ? (
                  <p className="text-[12.5px] text-text-muted">Betöltés…</p>
                ) : (
                  <div className="flex max-h-40 flex-wrap gap-x-4 gap-y-1 overflow-y-auto">
                    {emberek.map((e) => (
                      <label key={e.id} className="flex items-center gap-1.5 text-[12.5px] text-text-secondary">
                        <input
                          type="checkbox"
                          checked={kezelok.includes(e.id)}
                          onChange={() => void kezeloValt(e.id)}
                        />
                        {e.nev}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="mt-4 flex justify-end border-t border-border pt-3">
              <button
                type="button"
                disabled={busy}
                onClick={() => setNyitva(false)}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Bezárás
              </button>
            </div>
          </div>
        </ModalReteg>
      )}
    </>
  );
}
