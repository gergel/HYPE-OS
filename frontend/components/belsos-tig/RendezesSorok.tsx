"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Upload } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { formatHuf } from "@/lib/penz";
import type { BelsosRendezesHonap } from "@/lib/api";

const LEZART = ["Kiküldve", "Kész"];
const HONAPOK = ["január", "február", "március", "április", "május", "június", "július", "augusztus", "szeptember", "október", "november", "december"];

async function hiba(res: Response): Promise<string> {
  const d = await res.json().catch(() => null);
  return typeof d?.detail === "string" ? d.detail : `Sikertelen (${res.status})`;
}

/** Egy munkatárs egy évének 12 hónapja a VISSZAMENŐLEGES RENDEZÉSHEZ (a
 * felhasználó kérése): hónaponként az összeg, a TIG (feltöltés - kiküldés
 * nélkül), a számlák, a kifizetés (KIADÁS SOR NÉLKÜL, mert a pénz már a
 * Kiadások közt van), és az elcsúszott hónap kézi áthelyezése. Minden művelet
 * a meglévő Belsős TIG végpontokon megy (lásd backend
 * internal_performance_certificates.py), csak egy helyre gyűjtve. */
export function RendezesSorok({
  employeeId,
  ev,
  honapok,
  canEdit,
}: {
  employeeId: number;
  ev: number;
  honapok: BelsosRendezesHonap[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState<number | null>(null);
  const [uzenet, setUzenet] = useState<{ honap: number; szoveg: string; hiba: boolean } | null>(null);
  const [osszegek, setOsszegek] = useState<Record<number, string>>({});
  const [datumok, setDatumok] = useState<Record<number, string>>({});
  const [celok, setCelok] = useState<Record<number, string>>({});

  const alap = (h: number) => `/api/v1/belsos-tig/${employeeId}/${ev}/${h}`;

  async function futtat(h: number, fn: () => Promise<Response>, siker: string) {
    setBusy(h);
    setUzenet(null);
    try {
      const res = await fn();
      if (!res.ok) {
        setUzenet({ honap: h, szoveg: await hiba(res), hiba: true });
        return false;
      }
      setUzenet({ honap: h, szoveg: siker, hiba: false });
      router.refresh();
      return true;
    } catch (err) {
      setUzenet({ honap: h, szoveg: `Hálózati hiba: ${err}`, hiba: true });
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function feltolt(h: number, utvonal: "tig-fajl" | "szamla", fajlok: FileList | null) {
    if (!fajlok || fajlok.length === 0) return;
    for (const f of Array.from(fajlok)) {
      const fd = new FormData();
      fd.append("file", f);
      const ok = await futtat(
        h,
        () => authFetch(`${alap(h)}/${utvonal}`, { method: "POST", body: fd }),
        utvonal === "tig-fajl" ? "TIG feltöltve (a hónap lezárva, kiküldés nélkül)." : "Számla feltöltve.",
      );
      if (!ok) break;
    }
  }

  async function athelyez(h: number) {
    const cel = celok[h];
    if (!cel) return;
    const [celEv, celHonap] = cel.split("-").map(Number);
    const kuld = (csere: boolean) =>
      authFetch(`${alap(h)}/athelyezes`, {
        method: "POST",
        body: JSON.stringify({ cel_ev: celEv, cel_honap: celHonap, csere }),
      });
    setBusy(h);
    setUzenet(null);
    try {
      let res = await kuld(false);
      if (res.status === 409) {
        const szoveg = await hiba(res);
        if (szoveg.includes("cserélheted")) {
          const ok = await confirm(`${szoveg}\n\nCseréljen helyet a két hónap TIG-je (a tételeikkel együtt)?`, {
            megerositoCimke: "Csere",
          });
          if (!ok) return;
          res = await kuld(true);
        } else {
          setUzenet({ honap: h, szoveg, hiba: true });
          return;
        }
      }
      if (!res.ok) {
        setUzenet({ honap: h, szoveg: await hiba(res), hiba: true });
        return;
      }
      setCelok((c) => ({ ...c, [h]: "" }));
      router.refresh();
    } finally {
      setBusy(null);
    }
  }

  // Az áthelyezés célja: az év hónapjai + a szomszédos év széle.
  const celOpciok = [
    { value: `${ev - 1}-12`, label: `${ev - 1}. december` },
    ...HONAPOK.map((n, i) => ({ value: `${ev}-${i + 1}`, label: `${ev}. ${n}` })),
    { value: `${ev + 1}-1`, label: `${ev + 1}. január` },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="os-table min-w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-border">
            <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Hónap</th>
            <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Összeg (nettó)</th>
            <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">TIG</th>
            <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Számlák</th>
            <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Kifizetés</th>
            <th className="py-1.5 text-left font-medium text-text-secondary">Hónap javítása</th>
          </tr>
        </thead>
        <tbody>
          {honapok.map((m) => {
            const h = m.honap;
            const vanTig = m.tig_id !== null;
            const ures = !vanTig && !m.belsos;
            const lezart = LEZART.includes(m.allapot ?? "");
            const fizetesAkadaly = m.kell_tig
              ? !lezart
                ? "előbb a TIG-et töltsd fel"
                : m.szamlak.length === 0
                  ? "előbb a számlát töltsd fel"
                  : null
              : !m.netto_osszeg
                ? "előbb az összeget add meg"
                : null;
            const osszegSzerkesztheto = canEdit && !m.van_tetel && m.kiadas_id === null && (vanTig || m.belsos);
            return (
              <tr key={h} className={`border-b border-border align-top last:border-0 ${ures ? "opacity-50" : ""}`}>
                <td className="py-2 pr-4">
                  <span className="font-medium text-text-primary">{m.honap_nev}</span>
                  {m.allapot && (
                    <span className="ml-2 align-middle">
                      <StatusBadge label={m.allapot} tone={lezart ? "success" : m.allapot === "Kihagyva" ? "neutral" : "warning"} />
                    </span>
                  )}
                  {!m.belsos && vanTig && <span className="mt-0.5 block text-[11.5px] text-text-muted">nem volt belsős (időszak szerint)</span>}
                  {!m.kell_tig && m.belsos && <span className="mt-0.5 block text-[11.5px] text-text-muted">bejelentett alkalmazott</span>}
                  {vanTig && (
                    <Link href={`/belsos-tig/${employeeId}/${ev}/${h}`} className="mt-0.5 block text-[11.5px] text-text-accent hover:underline">
                      Hónap oldala
                    </Link>
                  )}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {osszegSzerkesztheto ? (
                    <span className="inline-flex items-center gap-1">
                      <input
                        inputMode="decimal"
                        value={osszegek[h] ?? (m.netto_osszeg != null ? String(m.netto_osszeg) : "")}
                        onChange={(e) => setOsszegek((o) => ({ ...o, [h]: e.target.value.replace(/[^\d.]/g, "") }))}
                        placeholder="–"
                        className="w-[110px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-right text-[13px]"
                      />
                      {osszegek[h] !== undefined && osszegek[h] !== String(m.netto_osszeg ?? "") && osszegek[h] !== "" && (
                        <button
                          type="button"
                          disabled={busy === h}
                          onClick={() =>
                            void futtat(
                              h,
                              () =>
                                authFetch(`${alap(h)}/rendezes-osszeg`, {
                                  method: "POST",
                                  body: JSON.stringify({ netto_osszeg: Number(osszegek[h]) }),
                                }),
                              "Összeg mentve.",
                            ).then((ok) => ok && setOsszegek((o) => { const u = { ...o }; delete u[h]; return u; }))
                          }
                          className="text-[12px] text-text-accent hover:underline disabled:opacity-50"
                        >
                          Mentés
                        </button>
                      )}
                    </span>
                  ) : m.netto_osszeg != null ? (
                    formatHuf(m.netto_osszeg)
                  ) : (
                    <span className="text-text-muted">–</span>
                  )}
                  {m.van_tetel && <span className="mt-0.5 block text-[11px] text-text-muted">tételekből</span>}
                </td>
                <td className="py-2 pr-4">
                  {m.tig_fajl_url && (
                    <a href={m.tig_fajl_url} target="_blank" rel="noreferrer" className="block text-text-accent hover:underline">
                      {m.kell_tig ? "TIG" : "Jegyzék"}
                    </a>
                  )}
                  {canEdit && (m.belsos || vanTig) && (
                    <label className={`inline-flex cursor-pointer items-center gap-1 text-[12px] text-text-secondary hover:text-text-primary ${busy === h ? "opacity-50" : ""}`}>
                      <Upload size={12} /> {m.tig_fajl_url ? "Csere" : "Feltöltés"}
                      <input type="file" accept="application/pdf,image/*" className="hidden" disabled={busy === h}
                        onChange={(e) => { const f = e.target.files; void feltolt(h, "tig-fajl", f); e.target.value = ""; }} />
                    </label>
                  )}
                </td>
                <td className="py-2 pr-4">
                  {m.kell_tig ? (
                    <>
                      {m.szamlak.map((sz) => (
                        <a key={sz.id} href={sz.url} target="_blank" rel="noreferrer" className="block max-w-[180px] truncate text-text-accent hover:underline">
                          {sz.filename}
                        </a>
                      ))}
                      {canEdit && (m.belsos || vanTig) && (
                        <label className={`inline-flex cursor-pointer items-center gap-1 text-[12px] text-text-secondary hover:text-text-primary ${busy === h ? "opacity-50" : ""}`}>
                          <Upload size={12} /> Számla
                          <input type="file" multiple accept="application/pdf,image/*" className="hidden" disabled={busy === h}
                            onChange={(e) => { const f = e.target.files; void feltolt(h, "szamla", f); e.target.value = ""; }} />
                        </label>
                      )}
                    </>
                  ) : (
                    <span className="text-text-muted">–</span>
                  )}
                </td>
                <td className="py-2 pr-4">
                  {m.szamla_kifizetve ? (
                    <span className="flex flex-col">
                      <StatusBadge label={`Kifizetve${m.utalas_datuma ? ` ${m.utalas_datuma}` : ""}`} tone="success" />
                      <span className="mt-0.5 text-[11px] text-text-muted">
                        {m.kiadas_id ? "a Kiadások közt is (ekkor jött létre)" : "Kiadás sor nélkül"}
                      </span>
                    </span>
                  ) : vanTig && canEdit ? (
                    <span className="flex flex-col gap-1">
                      <input
                        type="date"
                        value={datumok[h] ?? m.utalas_datuma ?? m.fizetesi_hatarido ?? ""}
                        onChange={(e) => setDatumok((d) => ({ ...d, [h]: e.target.value }))}
                        className="w-[150px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px]"
                      />
                      <button
                        type="button"
                        disabled={busy === h || fizetesAkadaly !== null || !(datumok[h] ?? m.utalas_datuma ?? m.fizetesi_hatarido)}
                        title={fizetesAkadaly ?? "Kifizetettnek jelöli - a Kiadásokba NEM kerül (már benne van)"}
                        onClick={() =>
                          void futtat(
                            h,
                            () =>
                              authFetch(`${alap(h)}/szamla-kifizetve`, {
                                method: "POST",
                                body: JSON.stringify({
                                  kiadasba_kerul: false,
                                  kifizetes_datuma: datumok[h] ?? m.utalas_datuma ?? m.fizetesi_hatarido,
                                }),
                              }),
                            "Kifizetettnek jelölve (Kiadás sor nélkül).",
                          )
                        }
                        className="w-fit rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                      >
                        Kifizetve (kiadás nélkül)
                      </button>
                      {fizetesAkadaly && <span className="text-[11px] text-text-muted">{fizetesAkadaly}</span>}
                    </span>
                  ) : (
                    <span className="text-text-muted">–</span>
                  )}
                </td>
                <td className="py-2">
                  {Object.keys(m.datumok_szerint).length > 0 && (
                    <span className="mb-1 block text-[11.5px] text-text-warning">
                      A dátumai szerint:{" "}
                      {Object.entries(m.datumok_szerint).map(([forras, honap]) => `${forras} → ${honap}`).join(", ")}
                    </span>
                  )}
                  {m.honap_rogzitve && <span className="mb-1 block text-[11.5px] text-text-muted">kézzel rögzített hónap</span>}
                  {vanTig && canEdit && (
                    <span className="flex flex-wrap items-center gap-1">
                      <select
                        value={celok[h] ?? ""}
                        onChange={(e) => setCelok((c) => ({ ...c, [h]: e.target.value }))}
                        className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-1 text-[12px]"
                      >
                        <option value="">Áthelyezés ide…</option>
                        {celOpciok
                          .filter((o) => o.value !== `${ev}-${h}`)
                          .map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                      </select>
                      {celok[h] && (
                        <button type="button" disabled={busy === h} onClick={() => void athelyez(h)}
                          className="text-[12px] text-text-accent hover:underline disabled:opacity-50">
                          Áthelyezés
                        </button>
                      )}
                      {Object.keys(m.datumok_szerint).length > 0 && !m.honap_rogzitve && (
                        <button
                          type="button"
                          disabled={busy === h}
                          title="Ez a helyes hónap - a dátumai többé nem tolják el"
                          onClick={() =>
                            void futtat(
                              h,
                              () =>
                                authFetch(`${alap(h)}/athelyezes`, {
                                  method: "POST",
                                  body: JSON.stringify({ cel_ev: ev, cel_honap: h }),
                                }),
                              "Rögzítve: ez a helyes hónap.",
                            )
                          }
                          className="text-[12px] text-text-secondary hover:underline disabled:opacity-50"
                        >
                          Ez a jó hónap
                        </button>
                      )}
                    </span>
                  )}
                  {uzenet?.honap === h && (
                    <span className={`mt-1 block max-w-[280px] whitespace-normal text-[11.5px] ${uzenet.hiba ? "text-text-danger" : "text-text-success"}`}>
                      {uzenet.szoveg}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
