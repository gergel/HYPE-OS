"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type Payload = Record<string, unknown>;
type Tetel = { nev?: string; project_nev?: string; mezok?: Record<string, unknown>; [k: string]: unknown };

const MEZO_CIMKE: Record<string, string> = {
  ceg_neve: "Cég / név",
  szekhely: "Székhely",
  adoszam: "Adószám",
  vallalkozas_kepviseloje: "Képviselő",
  vallalkozas_nyilvantartasi_szam: "Nyilvántartási szám",
  megbizas_targya: "Megbízás tárgya",
  netto_osszeg: "Nettó összeg (Ft)",
  teljesites_szoveg: "Teljesítés ideje",
  plusz_afa: "+ÁFA (true/false)",
  to: "Címzett(ek) (vesszővel)",
  subject: "Tárgy",
  html_body: "Levél szövege",
  cel_tipus: "Céltípus",
  cel_project_code_id: "Projektkód azonosító",
  netto: "Nettó",
  brutto: "Bruttó",
};

/** Mezők, amik a TIG/szerződés tételeiben szerkeszthetők (a sorrend is ez). */
const TETEL_MEZOK = [
  "ceg_neve",
  "megbizas_targya",
  "netto_osszeg",
  "teljesites_szoveg",
  "szekhely",
  "adoszam",
  "vallalkozas_kepviseloje",
  "vallalkozas_nyilvantartasi_szam",
  "plusz_afa",
];
/** Felső szintű, szerkeszthető mezők (e-mail, számla). */
const FELSO_MEZOK = ["to", "subject", "html_body", "cel_tipus", "cel_project_code_id"];

function szovegge(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

function vissza(kulcs: string, s: string, eredeti: unknown): unknown {
  const t = s.trim();
  if (kulcs === "to") return t ? t.split(",").map((x) => x.trim()).filter(Boolean) : [];
  if (t === "") return null;
  if (kulcs === "plusz_afa") return t === "true" || t === "igen";
  if (typeof eredeti === "number" || kulcs === "netto_osszeg" || kulcs === "cel_project_code_id") {
    const n = Number(t.replace(/\s/g, "").replace(",", "."));
    return Number.isFinite(n) ? n : t;
  }
  return t;
}

/** HYRON — javaslat szerkesztése (kliens).
 *
 * Amit itt módosítasz, az JAVÍTÁSKÉNT rögzül (ebből tanul HYRON), és új
 * javaslat készül — a régi leváltódik, a függő jóváhagyása lejár. Az új
 * javaslat ugyanazon az ellenőrzésen és szabályrendszeren megy át. */
export function AdminJavaslatSzerkeszto({
  taskId,
  proposalId,
  payload,
}: {
  taskId: number;
  proposalId: number;
  payload: Payload;
}) {
  const router = useRouter();
  const [nyitva, setNyitva] = useState(false);
  const tetelekEredeti = Array.isArray(payload.tetelek) ? (payload.tetelek as Tetel[]) : null;
  const [tetelek, setTetelek] = useState<Record<string, string>[]>(
    (tetelekEredeti ?? []).map((t) => Object.fromEntries(TETEL_MEZOK.map((m) => [m, szovegge(t.mezok?.[m])]))),
  );
  const felsoKulcsok = FELSO_MEZOK.filter((k) => k in payload);
  const [felso, setFelso] = useState<Record<string, string>>(
    Object.fromEntries(felsoKulcsok.map((k) => [k, szovegge(payload[k])])),
  );
  const [magyarazat, setMagyarazat] = useState("");
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);

  if (!tetelekEredeti && felsoKulcsok.length === 0) return null;

  async function mentes() {
    setHiba(null);
    const uj: Payload = { ...payload };
    for (const k of felsoKulcsok) uj[k] = vissza(k, felso[k] ?? "", payload[k]);
    if (tetelekEredeti) {
      uj.tetelek = tetelekEredeti.map((t, i) => {
        const mezok: Record<string, unknown> = { ...(t.mezok ?? {}) };
        for (const m of TETEL_MEZOK) {
          const v = vissza(m, tetelek[i]?.[m] ?? "", t.mezok?.[m]);
          if (v === null) delete mezok[m];
          else mezok[m] = v;
        }
        const forrasok = { ...((t.forrasok as Record<string, string>) ?? {}) };
        for (const m of TETEL_MEZOK) {
          if (szovegge(t.mezok?.[m]) !== (tetelek[i]?.[m] ?? "")) forrasok[m] = "ember (szerkesztés)";
        }
        return { ...t, mezok, forrasok };
      });
    }
    setFolyamatban(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/proposals/${proposalId}/edit`, {
        method: "POST",
        body: JSON.stringify({ payload: uj, magyarazat: magyarazat.trim() || null }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => ({}))) as { detail?: string };
        setHiba(typeof d.detail === "string" ? d.detail : "A mentés nem sikerült.");
        return;
      }
      setNyitva(false);
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  const input =
    "w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12.5px] text-text-primary placeholder:text-text-muted";

  if (!nyitva) {
    return (
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className="mt-2 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1 text-[12px] font-medium text-text-primary hover:bg-surface-4"
      >
        Javaslat szerkesztése
      </button>
    );
  }

  return (
    <div className="mt-2 rounded-[var(--radius)] border border-border bg-surface-2 p-3">
      <p className="mb-2 text-[12px] text-text-muted">
        A módosításod javításként rögzül (ebből tanul HYRON), és új javaslat készül a régi helyett.
      </p>
      {hiba && <div className="mb-2 rounded-[var(--radius)] bg-bg-danger px-2 py-1.5 text-[12px] text-text-danger">{hiba}</div>}

      {felsoKulcsok.map((k) => (
        <label key={k} className="mb-2 flex flex-col gap-1 text-[11.5px] text-text-muted">
          {MEZO_CIMKE[k] ?? k}
          {k === "html_body" ? (
            <textarea
              rows={6}
              value={felso[k] ?? ""}
              onChange={(e) => setFelso((p) => ({ ...p, [k]: e.target.value }))}
              className={input}
            />
          ) : (
            <input value={felso[k] ?? ""} onChange={(e) => setFelso((p) => ({ ...p, [k]: e.target.value }))} className={input} />
          )}
        </label>
      ))}

      {tetelekEredeti?.map((t, i) => (
        <div key={i} className="mb-3 rounded-[var(--radius)] border border-border bg-surface-3 p-2.5">
          <p className="mb-1.5 text-[12.5px] font-medium text-text-primary">
            {t.nev} <span className="text-text-muted">· {t.project_nev}</span>
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {TETEL_MEZOK.map((m) => (
              <label key={m} className="flex flex-col gap-1 text-[11.5px] text-text-muted">
                {MEZO_CIMKE[m] ?? m}
                <input
                  value={tetelek[i]?.[m] ?? ""}
                  onChange={(e) =>
                    setTetelek((p) => p.map((x, j) => (j === i ? { ...x, [m]: e.target.value } : x)))
                  }
                  className={input}
                />
              </label>
            ))}
          </div>
        </div>
      ))}

      <input
        value={magyarazat}
        onChange={(e) => setMagyarazat(e.target.value)}
        placeholder="Miért módosítottad? (opcionális — segít a tanulásban)"
        className={`${input} mb-2`}
      />
      <div className="flex gap-2">
        <button
          type="button"
          disabled={folyamatban}
          onClick={mentes}
          className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[12.5px] font-medium text-text-accent disabled:opacity-50"
        >
          {folyamatban ? "Mentés…" : "Mentés új javaslatként"}
        </button>
        <button
          type="button"
          onClick={() => setNyitva(false)}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-4"
        >
          Mégse
        </button>
      </div>
    </div>
  );
}
