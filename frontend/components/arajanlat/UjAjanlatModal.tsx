"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { ModalReteg } from "@/components/ModalReteg";
import { MARKAK, type Ajanlat, type Sablon, type Ugyfel, ft, hivas, kuld } from "./quote";

/** Új árajánlat: márka → ügyfél (kereshető, új is felvehető) → projekt,
 * dátum, helyszín → sablon-kártya vagy „Üres ajánlat”. A létrehozás után a
 * szerkesztő nyílik. */
export function UjAjanlatModal({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [brand, setBrand] = useState<"HYPE" | "CB">("HYPE");
  const [ugyfel, setUgyfel] = useState<Ugyfel | null>(null);
  const [projekt, setProjekt] = useState("");
  const [tol, setTol] = useState("");
  const [ig, setIg] = useState("");
  const [helyszin, setHelyszin] = useState("");
  const [sablonok, setSablonok] = useState<Sablon[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => {
    hivas<Sablon[]>("/templates")
      .then(setSablonok)
      .catch((e: Error) => setHiba(e.message));
  }, []);

  async function letrehoz(templateId: number | null) {
    setBusy(true);
    setHiba(null);
    try {
      const q = await kuld<Ajanlat>("", "POST", {
        template_id: templateId,
        brand,
        client_id: ugyfel?.id ?? null,
        project_name: projekt.trim(),
        event_date_from: tol || null,
        event_date_to: ig || null,
        location: helyszin.trim() || null,
      });
      // A felugró ablak záráskor egy history.back()-kel veszi le a saját
      // előzmény-rétegét (lásd useModalVisszaVedelem) - ha előbb navigálnánk,
      // az a visszalépés az új oldalról visszadobna a listára. Ezért: bezár,
      // megvárja a visszalépést, és csak utána nyitja a szerkesztőt.
      let ment = false;
      const menj = () => {
        if (ment) return;
        ment = true;
        router.push(`/arajanlatok/${q.id}`);
      };
      window.addEventListener("popstate", menj, { once: true });
      onClose();
      setTimeout(menj, 600);
    } catch (e) {
      setHiba((e as Error).message);
      setBusy(false);
    }
  }

  const sajatMarka = sablonok ?? [];

  return (
    <ModalReteg onClose={onClose}>
      <div className="w-full max-w-[920px] rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-text-primary">Új árajánlat</h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-text-muted hover:bg-surface-3" aria-label="Bezárás">
            <X size={16} />
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="flex flex-col gap-1 text-[12px] text-text-muted">
            Márka
            <div className="flex gap-1.5">
              {MARKAK.map((m) => (
                <button
                  key={m.ertek}
                  type="button"
                  onClick={() => setBrand(m.ertek)}
                  className={`flex-1 rounded-[var(--radius)] border px-3 py-1.5 text-[13px] ${
                    brand === m.ertek ? "border-text-accent bg-bg-accent text-text-accent" : "border-border text-text-secondary hover:bg-surface-3"
                  }`}
                >
                  {m.cimke}
                </button>
              ))}
            </div>
          </div>
          <UgyfelValaszto ertek={ugyfel} onValaszt={setUgyfel} />
          <label className="flex flex-col gap-1 text-[12px] text-text-muted md:col-span-2">
            Projekt neve
            <input
              className="field"
              value={projekt}
              onChange={(e) => setProjekt(e.target.value)}
              placeholder="pl. Céges évzáró gála"
              autoFocus
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1 text-[12px] text-text-muted">
              Dátum (-tól)
              <input type="date" className="field" value={tol} onChange={(e) => setTol(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-[12px] text-text-muted">
              (-ig)
              <input type="date" className="field" value={ig} min={tol || undefined} onChange={(e) => setIg(e.target.value)} />
            </label>
          </div>
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Helyszín
            <input className="field" value={helyszin} onChange={(e) => setHelyszin(e.target.value)} placeholder="pl. Budapest" />
          </label>
        </div>

        <p className="mb-2 mt-5 text-[12px] font-medium uppercase tracking-wide text-text-muted">Sablon</p>
        {hiba && <p className="mb-2 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</p>}
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <button
            type="button"
            disabled={busy}
            onClick={() => letrehoz(null)}
            className="flex min-h-[112px] flex-col items-start rounded-[var(--radius)] border border-dashed border-border p-3 text-left hover:bg-surface-3 disabled:opacity-50"
          >
            <span className="text-[14px] font-medium text-text-primary">Üres ajánlat</span>
            <span className="mt-1 text-[12px] text-text-muted">Tételek nélkül indul - a katalógusból egy kattintással töltöd fel.</span>
          </button>
          {sablonok === null && <p className="p-3 text-[13px] text-text-muted">Sablonok betöltése…</p>}
          {sajatMarka.map((s) => (
            <button
              key={s.id}
              type="button"
              disabled={busy}
              onClick={() => letrehoz(s.id)}
              className="flex min-h-[112px] flex-col items-start rounded-[var(--radius)] border border-border bg-surface-2 p-3 text-left transition-colors hover:border-text-accent hover:bg-surface-3 disabled:opacity-50"
            >
              <span className="flex w-full items-start justify-between gap-2">
                <span className="text-[14px] font-medium text-text-primary">{s.name}</span>
                {s.pricing_mode === "monthly" && (
                  <span className="shrink-0 rounded bg-bg-blue px-1.5 py-0.5 text-[11px] text-text-blue">havidíjas</span>
                )}
              </span>
              {s.description && <span className="mt-1 line-clamp-2 text-[12px] text-text-muted">{s.description}</span>}
              <span className="mt-auto pt-2 text-[12px] text-text-secondary">
                {s.typical_total ? <>Tipikusan ~{ft(s.typical_total)} · </> : null}
                alap: {ft(s.base_total)} · {s.item_count} sor
              </span>
            </button>
          ))}
        </div>
        {sablonok !== null && sablonok.length === 0 && (
          <p className="mt-2 text-[12.5px] text-text-muted">
            Még nincs sablon. A Katalógus fülön az „Alapadatok betöltése” gombbal jön be a 10 alap sablon.
          </p>
        )}
      </div>
    </ModalReteg>
  );
}

/** Kereshető ügyfélválasztó a meglévő ügyfelekből; ha nincs találat, a beírt
 * névvel új ügyfél vehető fel. */
export function UgyfelValaszto({
  ertek,
  onValaszt,
  tiltva = false,
}: {
  ertek: Ugyfel | { id: number; nev: string } | null;
  onValaszt: (u: Ugyfel | null) => void;
  tiltva?: boolean;
}) {
  const [szoveg, setSzoveg] = useState("");
  const [nyitva, setNyitva] = useState(false);
  const [talalatok, setTalalatok] = useState<Ugyfel[]>([]);
  const [hiba, setHiba] = useState<string | null>(null);
  const idozito = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!nyitva) return;
    if (idozito.current) clearTimeout(idozito.current);
    idozito.current = setTimeout(() => {
      hivas<Ugyfel[]>(`/clients?q=${encodeURIComponent(szoveg)}&limit=12`)
        .then(setTalalatok)
        .catch(() => setTalalatok([]));
    }, 200);
  }, [szoveg, nyitva]);

  async function ujUgyfel() {
    setHiba(null);
    try {
      const u = await kuld<Ugyfel>("/clients", "POST", { nev: szoveg.trim() });
      onValaszt(u);
      setNyitva(false);
      setSzoveg("");
    } catch (e) {
      setHiba((e as Error).message);
    }
  }

  const pontos = talalatok.some((t) => t.nev.toLowerCase() === szoveg.trim().toLowerCase());

  return (
    <div className="relative flex flex-col gap-1 text-[12px] text-text-muted">
      Ügyfél
      {ertek && !nyitva ? (
        <div className="flex items-center gap-2">
          <span className="field flex-1 truncate text-text-primary">{ertek.nev}</span>
          {!tiltva && (
            <button type="button" className="btn btn-ghost text-[12px]" onClick={() => setNyitva(true)}>
              Csere
            </button>
          )}
        </div>
      ) : (
        <input
          className="field"
          value={szoveg}
          disabled={tiltva}
          placeholder="Keresés név szerint…"
          onFocus={() => setNyitva(true)}
          onBlur={() => setTimeout(() => setNyitva(false), 180)}
          onChange={(e) => setSzoveg(e.target.value)}
          autoFocus={nyitva && !!ertek}
        />
      )}
      {nyitva && (
        <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-64 overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-1 py-1 shadow-lg">
          {talalatok.map((t) => (
            <button
              key={t.id}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onValaszt(t);
                setNyitva(false);
                setSzoveg("");
              }}
              className="block w-full px-3 py-1.5 text-left text-[13px] text-text-primary hover:bg-surface-3"
            >
              {t.nev}
              {t.adoszam && <span className="ml-2 text-[11.5px] text-text-muted">{t.adoszam}</span>}
            </button>
          ))}
          {szoveg.trim() && !pontos && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={ujUgyfel}
              className="block w-full px-3 py-1.5 text-left text-[13px] text-text-accent hover:bg-surface-3"
            >
              + Új ügyfél: „{szoveg.trim()}”
            </button>
          )}
          {ertek && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onValaszt(null);
                setNyitva(false);
              }}
              className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-muted hover:bg-surface-3"
            >
              Ügyfél eltávolítása
            </button>
          )}
          {talalatok.length === 0 && !szoveg.trim() && (
            <p className="px-3 py-1.5 text-[12.5px] text-text-muted">Kezdd el gépelni az ügyfél nevét.</p>
          )}
        </div>
      )}
      {hiba && <span className="text-text-danger">{hiba}</span>}
    </div>
  );
}
