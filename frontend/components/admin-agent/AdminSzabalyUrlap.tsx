"use client";

import { useState } from "react";
import { authFetch } from "@/lib/authFetch";
import type { AdminRule } from "@/lib/api";
import { CEL_CIMKE, TIPUS_CIMKE } from "@/components/admin-agent/allapotok";

/** Lara — szabály kézi felvétele (kliens).
 *
 * A fejekben lévő szokások közvetlen beírása. A szabály VÁZLATKÉNT jön létre,
 * és csak értékelés után, élesítéssel lesz aktív. Ha partnerhez kötöd, csak
 * annál a partnernél jön elő; ha számlánál céltípust is megadsz, Lara
 * modell nélkül is kitölti vele az üres célt (az érkeztető javaslatát nem írja
 * felül). */
export function AdminSzabalyUrlap({ onLetrehozva }: { onLetrehozva: (r: AdminRule) => void }) {
  const [nyitva, setNyitva] = useState(false);
  const [hatokor, setHatokor] = useState("szamla");
  const [partner, setPartner] = useState("");
  const [celTipus, setCelTipus] = useState("");
  const [projektkod, setProjektkod] = useState("");
  const [cim, setCim] = useState("");
  const [tartalom, setTartalom] = useState("");
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);

  const input =
    "w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted";

  async function mentes() {
    setHiba(null);
    if (cim.trim().length < 3 || tartalom.trim().length < 3) {
      setHiba("Adj meg címet és leírást.");
      return;
    }
    setFolyamatban(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/rules", {
        method: "POST",
        body: JSON.stringify({
          hatokor,
          cim: cim.trim(),
          tartalom: tartalom.trim(),
          partner: partner.trim() || null,
          cel_tipus: hatokor === "szamla" && celTipus ? celTipus : null,
          projektkod: projektkod.trim() || null,
        }),
      });
      const d = (await res.json().catch(() => ({}))) as AdminRule & { detail?: unknown };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A szabály mentése nem sikerült.");
        return;
      }
      onLetrehozva(d);
      setPartner("");
      setCelTipus("");
      setProjektkod("");
      setCim("");
      setTartalom("");
      setNyitva(false);
    } finally {
      setFolyamatban(false);
    }
  }

  if (!nyitva) {
    return (
      <li>
        <button
          type="button"
          onClick={() => setNyitva(true)}
          className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent"
        >
          + Új szabály kézzel
        </button>
      </li>
    );
  }

  return (
    <li className="rounded-[var(--radius)] border border-border bg-surface-3 p-3">
      {hiba && <div className="mb-2 rounded-[var(--radius)] bg-bg-danger px-2.5 py-1.5 text-[12.5px] text-text-danger">{hiba}</div>}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-[12px] text-text-muted">
          Feladattípus
          <select value={hatokor} onChange={(e) => setHatokor(e.target.value)} className={input}>
            {Object.entries(TIPUS_CIMKE).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-text-muted">
          Partner (opcionális — csak rá vonatkozik)
          <input value={partner} onChange={(e) => setPartner(e.target.value)} placeholder="pl. Turcsik Márk EV" className={input} />
        </label>
        {hatokor === "szamla" && (
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Hová kerüljön a számlája (opcionális, partnerrel)
            <select value={celTipus} onChange={(e) => setCelTipus(e.target.value)} className={input}>
              <option value="">— csak szöveges útmutatás —</option>
              {Object.entries(CEL_CIMKE).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="flex flex-col gap-1 text-[12px] text-text-muted">
          Projektkód (opcionális)
          <input value={projektkod} onChange={(e) => setProjektkod(e.target.value)} placeholder="pl. HYPE26-0012" className={input} />
        </label>
      </div>
      <label className="mt-2 flex flex-col gap-1 text-[12px] text-text-muted">
        Cím
        <input value={cim} onChange={(e) => setCim(e.target.value)} placeholder="pl. Turcsik Márk számlái a forgatási kódra" className={input} />
      </label>
      <label className="mt-2 flex flex-col gap-1 text-[12px] text-text-muted">
        A szabály (így magyaráznád egy új kollégának)
        <textarea
          rows={3}
          value={tartalom}
          onChange={(e) => setTartalom(e.target.value)}
          placeholder="pl. A számláit mindig új kiadásként vesszük fel azon a projektkódon, amelyik forgatáson dolgozott; ha a számlán nincs kód, kérdezz rá."
          className={input}
        />
      </label>
      <p className="mt-2 text-[11.5px] text-text-muted">
        Vázlatként mentődik. Élesíteni a Szabály-jelöltek közül lehet, sikeres értékelés (Tanulás → 3. Értékelés) után.
        {hatokor === "szamla" && celTipus
          ? " Élesítés után Lara ennél a partnernél modell nélkül is ezt a célt javasolja, ha az érkeztető nem döntött."
          : ""}
      </p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          disabled={folyamatban}
          onClick={mentes}
          className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
        >
          {folyamatban ? "Mentés…" : "Szabály mentése (vázlat)"}
        </button>
        <button
          type="button"
          onClick={() => setNyitva(false)}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-4"
        >
          Mégse
        </button>
      </div>
    </li>
  );
}
