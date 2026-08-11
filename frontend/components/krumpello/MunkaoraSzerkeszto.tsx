"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { ModalReteg } from "@/components/ModalReteg";
import { useConfirm } from "@/components/ConfirmProvider";
import { KeresosSelect } from "@/components/KeresosSelect";
import { formatFt } from "@/lib/ido";
import type { KrumpelloDolgozo, KrumpelloMunkaora } from "@/lib/api";

/** Egy munkanap felvitele/javítása, plusz új dolgozó felvétele.
 *
 * A dolgozó itt vehető fel, nem külön oldalon: az első munkanapja rögzítésekor
 * derül ki, hogy egyáltalán van ilyen ember - egy külön "dolgozók" oldal csak
 * egy fölösleges lépés lenne a valódi teendő előtt. */
export function MunkaoraSzerkeszto({
  dolgozok,
  munkaora,
}: {
  dolgozok: KrumpelloDolgozo[];
  munkaora?: KrumpelloMunkaora;
}) {
  const [nyitva, setNyitva] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className={munkaora ? "text-[12.5px] text-text-accent hover:underline" : "btn btn-primary !text-[13px]"}
      >
        {munkaora ? "Szerkesztés" : "+ Munkanap rögzítése"}
      </button>
      {nyitva && <MunkaoraUrlap dolgozok={dolgozok} munkaora={munkaora} onBezar={() => setNyitva(false)} />}
    </>
  );
}

const UJ_DOLGOZO = "__uj__";

function MunkaoraUrlap({
  dolgozok,
  munkaora,
  onBezar,
}: {
  dolgozok: KrumpelloDolgozo[];
  munkaora?: KrumpelloMunkaora;
  onBezar: () => void;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [dolgozoId, setDolgozoId] = useState<string>(munkaora ? String(munkaora.dolgozo_id) : "");
  const [ujNev, setUjNev] = useState("");
  const [datum, setDatum] = useState(munkaora?.datum ?? new Date().toISOString().slice(0, 10));
  const [ora, setOra] = useState(munkaora?.ora != null ? String(munkaora.ora) : "");
  const [orabar, setOrabar] = useState(munkaora?.orabar != null ? String(munkaora.orabar) : "");
  const [fizetes, setFizetes] = useState(munkaora?.fizetes != null ? String(munkaora.fizetes) : "");
  const [borravalo, setBorravalo] = useState(munkaora?.borravalo != null ? String(munkaora.borravalo) : "");
  const [megjegyzes, setMegjegyzes] = useState(munkaora?.megjegyzes ?? "");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  // Az órabért a kiválasztott ember utolsó órabéréből ajánljuk - a szokásos
  // eset így egy kattintás, a béremelés meg egyszeri átírás.
  function dolgozoValtas(ertek: string | null) {
    const uj = ertek ?? "";
    setDolgozoId(uj);
    const d = dolgozok.find((x) => String(x.id) === uj);
    if (d?.alap_orabar != null && !orabar) setOrabar(String(d.alap_orabar));
  }

  // A fizetés magától kijön óra × órabérből, de a BEÍRT érték mindig erősebb
  // (kerekítés, megbeszélt átalány) - itt csak előnézetet mutatunk.
  const szamoltFizetes =
    ora.trim() && orabar.trim() && !Number.isNaN(Number(ora)) && !Number.isNaN(Number(orabar))
      ? Math.round(Number(ora) * Number(orabar))
      : null;

  async function mentes() {
    const ujEmber = dolgozoId === UJ_DOLGOZO;
    if (!dolgozoId || (ujEmber && !ujNev.trim())) {
      setHiba("Válaszd ki, ki dolgozott – vagy add meg az új ember nevét.");
      return;
    }
    setBusy(true);
    setHiba(null);
    const szam = (v: string) => (v.trim() === "" ? null : Number(v));
    try {
      let celId = Number(dolgozoId);
      if (ujEmber) {
        const res = await authFetch("/api/v1/krumpello/dolgozok", {
          method: "POST",
          body: JSON.stringify({ nev: ujNev.trim(), alap_orabar: szam(orabar) }),
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          setHiba(detail?.detail ?? `Nem sikerült felvenni a dolgozót (HTTP ${res.status})`);
          return;
        }
        celId = ((await res.json()) as KrumpelloDolgozo).id;
      }
      const res = await authFetch(
        munkaora ? `/api/v1/krumpello/munkaorak/${munkaora.id}` : "/api/v1/krumpello/munkaorak",
        {
          method: munkaora ? "PATCH" : "POST",
          body: JSON.stringify({
            dolgozo_id: celId,
            datum,
            ora: szam(ora),
            orabar: szam(orabar),
            fizetes: szam(fizetes),
            borravalo: szam(borravalo),
            megjegyzes: megjegyzes.trim() || null,
          }),
        },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      onBezar();
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function torles() {
    if (!munkaora) return;
    if (!(await confirm(`Törlöd ${munkaora.dolgozo_nev} ${munkaora.datum} napi sorát?`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/krumpello/munkaorak/${munkaora.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen törlés (HTTP ${res.status})`);
        return;
      }
      onBezar();
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  const mezoClass =
    "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

  return (
    <ModalReteg onClose={busy ? undefined : onBezar}>
      <div
        role="dialog"
        aria-modal="true"
        className="krumpello-root w-full max-w-lg rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">
            {munkaora ? "Munkanap javítása" : "Munkanap rögzítése"}
          </h3>
        </div>

        <div className="max-h-[65vh] overflow-y-auto p-5">
          {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label className="text-[11px] text-text-muted">Ki dolgozott *</label>
              <KeresosSelect
                value={dolgozoId || null}
                options={[
                  ...dolgozok.map((d) => ({
                    value: String(d.id),
                    label: d.nev,
                    sublabel: d.alap_orabar != null ? `${formatFt(d.alap_orabar)}/óra` : undefined,
                  })),
                  { value: UJ_DOLGOZO, label: "+ Új dolgozó felvétele" },
                ]}
                onChange={dolgozoValtas}
                disabled={busy || !!munkaora}
                placeholder="Válassz…"
              />
            </div>
            {dolgozoId === UJ_DOLGOZO && (
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label className="text-[11px] text-text-muted">Az új dolgozó neve *</label>
                <input value={ujNev} onChange={(e) => setUjNev(e.target.value)} disabled={busy} className={mezoClass} />
              </div>
            )}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">Nap *</label>
              <input type="date" value={datum} onChange={(e) => setDatum(e.target.value)} disabled={busy} className={mezoClass} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">Ledolgozott óra</label>
              <input type="number" step="0.25" value={ora} onChange={(e) => setOra(e.target.value)} disabled={busy} className={mezoClass} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">Órabér</label>
              <input type="number" value={orabar} onChange={(e) => setOrabar(e.target.value)} disabled={busy} className={mezoClass} />
              <p className="text-[11px] text-text-muted">Az adott napra érvényes bér – a régi napokat nem írja át.</p>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">Fizetés</label>
              <input
                type="number"
                value={fizetes}
                onChange={(e) => setFizetes(e.target.value)}
                disabled={busy}
                placeholder={szamoltFizetes != null ? String(szamoltFizetes) : ""}
                className={mezoClass}
              />
              <p className="text-[11px] text-text-muted">
                {szamoltFizetes != null
                  ? `Üresen hagyva ${formatFt(szamoltFizetes)} lesz (óra × órabér).`
                  : "Üresen hagyva óra × órabér."}
              </p>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">Borravaló</label>
              <input type="number" value={borravalo} onChange={(e) => setBorravalo(e.target.value)} disabled={busy} className={mezoClass} />
            </div>
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label className="text-[11px] text-text-muted">Megjegyzés</label>
              <input value={megjegyzes} onChange={(e) => setMegjegyzes(e.target.value)} disabled={busy} className={mezoClass} />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-5 py-3">
          {munkaora && (
            <button type="button" onClick={torles} disabled={busy} className="btn btn-danger mr-auto">
              Törlés
            </button>
          )}
          <button type="button" onClick={onBezar} disabled={busy} className="btn btn-ghost">
            Mégse
          </button>
          <button type="button" onClick={mentes} disabled={busy} className="btn btn-primary">
            {busy ? "Mentés…" : "Mentés"}
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
