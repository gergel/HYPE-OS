"use client";

import { Fragment, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { huDatum } from "@/lib/huDate";
import { formatHuf } from "@/lib/penz";
import type { Kotelezettseg, KotelezettsegIdoszak } from "@/lib/api";

const HONAP_NEVEK = [
  "január", "február", "március", "április", "május", "június",
  "július", "augusztus", "szeptember", "október", "november", "december",
];

const TIPUS_NEVEK: Record<string, string> = {
  elofizetes: "Előfizetés",
  biztositas: "Biztosítás",
  forgalmi: "Forgalmi / műszaki",
  berlet: "Bérlet",
  egyeb: "Egyéb",
};

const CIKLUS_NEVEK: Record<string, string> = {
  havi: "Havi",
  eves: "Éves",
  egyszeri: "Egyszeri (határozott idejű)",
};

const PENZNEMEK = ["HUF", "EUR", "USD"];

/** Az állapot emberi neve és színe. A "hamarosan" azt jelenti, hogy a forduló
 * a kötelezettség saját figyelmeztetési idején belülre ért - ilyenkor már
 * feladat és értesítés is született róla (lásd backend
 * services/kotelezettseg.py). */
function allapotJelzo(k: Kotelezettseg) {
  if (!k.aktiv) return { label: "Inaktív", tone: "neutral" as const };
  if (k.allapot === "lejart") return { label: "Lejárt", tone: "danger" as const };
  if (k.allapot === "hamarosan") return { label: "Hamarosan lejár", tone: "warning" as const };
  if (k.allapot === "nincs_datum") return { label: "Nincs forduló", tone: "warning" as const };
  return { label: "Rendben", tone: "success" as const };
}

function penzzel(osszeg: number | null, penznem: string): string {
  if (osszeg == null) return "–";
  if (penznem === "HUF") return formatHuf(osszeg);
  return `${osszeg.toLocaleString("hu-HU")} ${penznem}`;
}

/** A forduló emberi leírása: "minden hónap 7-én", "minden szeptember 3-án",
 * vagy a konkrét dátum. */
function forduloSzoveg(k: Kotelezettseg): string {
  if (k.ciklus === "egyszeri") return k.kovetkezo_fordulo ? huDatum(k.kovetkezo_fordulo) : "–";
  if (k.ciklus === "havi") return k.fordulo_nap ? `minden hónap ${k.fordulo_nap}.` : "–";
  if (k.fordulo_honap && k.fordulo_nap) return `minden ${HONAP_NEVEK[k.fordulo_honap - 1]} ${k.fordulo_nap}.`;
  return k.kovetkezo_fordulo ? huDatum(k.kovetkezo_fordulo) : "–";
}

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

type UrlapAllapot = {
  nev: string;
  csomag: string;
  tipus: string;
  ciklus: string;
  fordulo_nap: string;
  fordulo_honap: string;
  kovetkezo_fordulo: string;
  osztaly: string;
  felelos_id: string;
  aktiv: boolean;
  ar_osszeg: string;
  ar_penznem: string;
  szamla_forras: string;
  kartya: string;
  megjegyzes: string;
  ertesites_napokkal: string;
};

function uresUrlap(alapTipus: string): UrlapAllapot {
  return {
    nev: "",
    csomag: "",
    tipus: alapTipus,
    ciklus: "havi",
    fordulo_nap: "",
    fordulo_honap: "",
    kovetkezo_fordulo: "",
    osztaly: "",
    felelos_id: "",
    aktiv: true,
    ar_osszeg: "",
    ar_penznem: "HUF",
    szamla_forras: "",
    kartya: "",
    megjegyzes: "",
    ertesites_napokkal: "14",
  };
}

function urlapBol(k: Kotelezettseg): UrlapAllapot {
  return {
    nev: k.nev,
    csomag: k.csomag ?? "",
    tipus: k.tipus,
    ciklus: k.ciklus,
    fordulo_nap: k.fordulo_nap != null ? String(k.fordulo_nap) : "",
    fordulo_honap: k.fordulo_honap != null ? String(k.fordulo_honap) : "",
    kovetkezo_fordulo: k.kovetkezo_fordulo ?? "",
    osztaly: k.osztaly ?? "",
    felelos_id: k.felelos_id != null ? String(k.felelos_id) : "",
    aktiv: k.aktiv,
    ar_osszeg: k.ar_osszeg != null ? String(k.ar_osszeg) : "",
    ar_penznem: k.ar_penznem,
    szamla_forras: k.szamla_forras ?? "",
    kartya: k.kartya ?? "",
    megjegyzes: k.megjegyzes ?? "",
    ertesites_napokkal: String(k.ertesites_napokkal ?? 14),
  };
}

/** Egy forduló sora: ide kell beírni, hogy PONTOSAN mennyibe került, és ide
 * kell feltölteni a számlát. A havi előfizetésnél ez havonta egy sor, az
 * évesnél évente egy - a backend nyitja őket (lásd ensure_idoszakok). */
function IdoszakSor({
  idoszak,
  szerkeszthet,
}: {
  idoszak: KotelezettsegIdoszak;
  szerkeszthet: boolean;
}) {
  const router = useRouter();
  const [osszeg, setOsszeg] = useState(idoszak.osszeg != null ? String(idoszak.osszeg) : "");
  const [hufOsszeg, setHufOsszeg] = useState(idoszak.huf_osszeg != null ? String(idoszak.huf_osszeg) : "");
  const [busy, setBusy] = useState(false);
  const [feltolt, setFeltolt] = useState(false);

  async function ment() {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/kotelezettsegek/idoszakok/${idoszak.id}`, {
        method: "PUT",
        body: JSON.stringify({
          osszeg: osszeg.trim() ? Number(osszeg) : null,
          huf_osszeg: hufOsszeg.trim() ? Number(hufOsszeg) : null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function szamlaFeltoltes(input: HTMLInputElement, files: File[]) {
    setFeltolt(true);
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        const res = await authFetch(
          `/api/v1/csatolmanyok/kotelezettsegIdoszak/${idoszak.id}?kategoria=szamla`,
          { method: "POST", body: fd },
        );
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          alert(`Sikertelen feltöltés (${file.name}): ${detail?.detail ?? res.status}`);
          break;
        }
      }
      router.refresh();
    } finally {
      setFeltolt(false);
      input.value = "";
    }
  }

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 pr-4 whitespace-nowrap text-text-primary">{huDatum(idoszak.esedekesseg)}</td>
      <td className="py-2 pr-4">
        {szerkeszthet ? (
          <input
            type="number"
            value={osszeg}
            onChange={(e) => setOsszeg(e.target.value)}
            onBlur={ment}
            disabled={busy}
            placeholder="Mennyibe került?"
            className={`${inputClass} w-[140px]`}
          />
        ) : (
          penzzel(idoszak.osszeg, idoszak.penznem)
        )}
      </td>
      <td className="py-2 pr-4">
        {/* Devizás terhelésnél a bankszámlán forint jelenik meg - azt csak
            beírni lehet, kiszámolni nem (nincs árfolyam-forrás). */}
        {idoszak.penznem !== "HUF" ? (
          szerkeszthet ? (
            <input
              type="number"
              value={hufOsszeg}
              onChange={(e) => setHufOsszeg(e.target.value)}
              onBlur={ment}
              disabled={busy}
              placeholder="Ft-ban"
              className={`${inputClass} w-[130px]`}
            />
          ) : (
            penzzel(idoszak.huf_osszeg, "HUF")
          )
        ) : (
          <span className="text-text-muted">–</span>
        )}
      </td>
      <td className="py-2 pr-4">
        {idoszak.szamla_db > 0 ? (
          <span className="text-text-secondary">{idoszak.szamla_db} db</span>
        ) : (
          <span className="text-text-muted">nincs</span>
        )}
        {szerkeszthet && (
          <label className="ml-2 cursor-pointer text-[12px] text-text-accent hover:underline">
            {feltolt ? "Feltöltés…" : "+ Számla"}
            <input
              type="file"
              multiple
              disabled={feltolt}
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                if (files.length > 0) szamlaFeltoltes(e.target, files);
              }}
              className="hidden"
            />
          </label>
        )}
      </td>
      <td className="py-2 text-right">
        {idoszak.hianyzik ? (
          <StatusBadge label={idoszak.hianyzik} tone="warning" />
        ) : (
          <StatusBadge label="Kész" tone="success" />
        )}
      </td>
    </tr>
  );
}

/** Kötelezettségek listája és szerkesztése.
 *
 * Ugyanez a komponens szolgálja ki az E-Rezsit (előfizetések) és a
 * Biztosítások oldalt - a különbség csak az, milyen típusú sorokat kap, és
 * milyen típussal nyílik az új felvitel űrlapja. */
export function KotelezettsegKezelo({
  kotelezettsegek,
  emberek,
  alapTipus = "elofizetes",
  tipusValaszthato = true,
  canEdit,
  canCreate,
  canDelete,
  autoId,
}: {
  kotelezettsegek: Kotelezettseg[];
  emberek: { id: number; full_name: string }[];
  alapTipus?: string;
  /** Az űrlapon lehessen-e típust váltani. Az autó lapján nem: ott a
   * határidő mindig a járműé. */
  tipusValaszthato?: boolean;
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
  /** Ha meg van adva, az új sor ehhez az autóhoz kerül. */
  autoId?: number;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitott, setNyitott] = useState<number | null>(null);
  const [urlap, setUrlap] = useState<UrlapAllapot | null>(null);
  const [szerkesztettId, setSzerkesztettId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  function ujat() {
    setSzerkesztettId(null);
    setUrlap(uresUrlap(alapTipus));
  }

  function szerkeszt(k: Kotelezettseg) {
    setSzerkesztettId(k.id);
    setUrlap(urlapBol(k));
  }

  function bezar() {
    setUrlap(null);
    setSzerkesztettId(null);
  }

  async function ment() {
    if (!urlap) return;
    if (!urlap.nev.trim()) {
      alert("Add meg a megnevezést.");
      return;
    }
    setBusy(true);
    try {
      const test = {
        nev: urlap.nev.trim(),
        csomag: urlap.csomag.trim() || null,
        tipus: urlap.tipus,
        ciklus: urlap.ciklus,
        fordulo_nap: urlap.fordulo_nap.trim() ? Number(urlap.fordulo_nap) : null,
        fordulo_honap: urlap.fordulo_honap.trim() ? Number(urlap.fordulo_honap) : null,
        kovetkezo_fordulo: urlap.kovetkezo_fordulo || null,
        osztaly: urlap.osztaly.trim() || null,
        felelos_id: urlap.felelos_id ? Number(urlap.felelos_id) : null,
        auto_id: autoId ?? null,
        aktiv: urlap.aktiv,
        ar_osszeg: urlap.ar_osszeg.trim() ? Number(urlap.ar_osszeg) : null,
        ar_penznem: urlap.ar_penznem,
        szamla_forras: urlap.szamla_forras.trim() || null,
        kartya: urlap.kartya.trim() || null,
        megjegyzes: urlap.megjegyzes.trim() || null,
        ertesites_napokkal: Number(urlap.ertesites_napokkal) || 14,
      };
      const res = await authFetch(
        szerkesztettId ? `/api/v1/kotelezettsegek/${szerkesztettId}` : "/api/v1/kotelezettsegek",
        { method: szerkesztettId ? "PUT" : "POST", body: JSON.stringify(test) },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      bezar();
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function torol(k: Kotelezettseg) {
    if (!(await confirm(`Törlöd ezt: "${k.nev}"? A fordulóihoz feltöltött számlák is elvesznek.`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/kotelezettsegek/${k.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {kotelezettsegek.length === 0 ? (
        <p className="mb-3 text-[13px] text-text-muted">Még nincs felvéve egy sem.</p>
      ) : (
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Megnevezés</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Forduló</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Következő</th>
              <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Ár</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Felelős</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Állapot</th>
              <th className="py-1.5 text-right font-medium text-text-secondary" />
            </tr>
          </thead>
          <tbody>
            {kotelezettsegek.map((k) => {
              const jelzo = allapotJelzo(k);
              const nyitva = nyitott === k.id;
              return (
                <Fragment key={k.id}>
                  <tr className="border-b border-border align-top">
                    <td className="py-2.5 pr-4">
                      <button
                        type="button"
                        onClick={() => setNyitott(nyitva ? null : k.id)}
                        className="flex items-start gap-1.5 text-left text-text-primary hover:text-text-accent"
                      >
                        {nyitva ? (
                          <ChevronDown size={14} className="mt-0.5 shrink-0 text-text-muted" />
                        ) : (
                          <ChevronRight size={14} className="mt-0.5 shrink-0 text-text-muted" />
                        )}
                        <span>
                          {k.nev}
                          {k.csomag && <span className="block text-[11.5px] text-text-muted">{k.csomag}</span>}
                        </span>
                      </button>
                    </td>
                    <td className="py-2.5 pr-4 text-text-secondary">
                      {forduloSzoveg(k)}
                      <span className="block text-[11.5px] text-text-muted">{CIKLUS_NEVEK[k.ciklus] ?? k.ciklus}</span>
                    </td>
                    <td className="py-2.5 pr-4 whitespace-nowrap text-text-secondary">
                      {k.kovetkezo_esedekesseg ? huDatum(k.kovetkezo_esedekesseg) : "–"}
                      {k.napok_hatra != null && (
                        <span className="block text-[11.5px] text-text-muted">
                          {k.napok_hatra < 0 ? `${-k.napok_hatra} napja lejárt` : `${k.napok_hatra} nap múlva`}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 pr-4 text-right whitespace-nowrap text-text-secondary">
                      {penzzel(k.ar_osszeg, k.ar_penznem)}
                    </td>
                    <td className="py-2.5 pr-4 text-text-secondary">{k.felelos_nev ?? "–"}</td>
                    <td className="py-2.5 pr-4">
                      <StatusBadge label={jelzo.label} tone={jelzo.tone} />
                      {k.nyitott_idoszakok > 0 && (
                        <span className="mt-1 block text-[11.5px] text-text-warning">
                          {k.nyitott_idoszakok} forduló nincs lezárva
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 text-right whitespace-nowrap">
                      {canEdit && (
                        <button
                          type="button"
                          onClick={() => szerkeszt(k)}
                          className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3"
                        >
                          Szerkesztés
                        </button>
                      )}
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => torol(k)}
                          disabled={busy}
                          title="Törlés"
                          className="ml-1 rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                  {nyitva && (
                    <tr className="border-b border-border bg-surface-2">
                      <td colSpan={7} className="px-3 py-4">
                        <div className="mb-3 grid grid-cols-1 gap-x-8 gap-y-1 text-[12.5px] text-text-muted sm:grid-cols-2">
                          {k.osztaly && (
                            <p>
                              Osztály: <span className="text-text-secondary">{k.osztaly}</span>
                            </p>
                          )}
                          {k.kartya && (
                            <p>
                              Terhelt kártya: <span className="text-text-secondary">{k.kartya}</span>
                            </p>
                          )}
                          {k.huf_becsles_honap != null && (
                            <p>
                              Becsült havi költség:{" "}
                              <span className="text-text-secondary">{formatHuf(k.huf_becsles_honap)}</span>
                            </p>
                          )}
                          {k.huf_becsles_ev != null && (
                            <p>
                              Becsült éves költség:{" "}
                              <span className="text-text-secondary">{formatHuf(k.huf_becsles_ev)}</span>
                            </p>
                          )}
                          <p>
                            Figyelmeztetés: <span className="text-text-secondary">{k.ertesites_napokkal} nappal előbb</span>
                          </p>
                          {k.szamla_forras && (
                            <p className="sm:col-span-2 whitespace-pre-line">
                              Számla forrása: <span className="text-text-secondary">{k.szamla_forras}</span>
                            </p>
                          )}
                          {k.megjegyzes && (
                            <p className="sm:col-span-2 whitespace-pre-line">
                              Megjegyzés: <span className="text-text-secondary">{k.megjegyzes}</span>
                            </p>
                          )}
                        </div>

                        <p className="t-label mb-1.5">Fordulók – mennyibe került, és hol a számla</p>
                        {k.idoszakok.length === 0 ? (
                          <p className="text-[12.5px] text-text-muted">
                            Még nincs esedékes forduló. Az első fordulónál magától megjelenik itt egy sor.
                          </p>
                        ) : (
                          <table className="w-full border-collapse text-[12.5px]">
                            <thead>
                              <tr className="border-b border-border">
                                <th className="py-1 pr-4 text-left font-medium text-text-muted">Forduló</th>
                                <th className="py-1 pr-4 text-left font-medium text-text-muted">Összeg</th>
                                <th className="py-1 pr-4 text-left font-medium text-text-muted">Ebből forint</th>
                                <th className="py-1 pr-4 text-left font-medium text-text-muted">Számla</th>
                                <th className="py-1 text-right font-medium text-text-muted">Állapot</th>
                              </tr>
                            </thead>
                            <tbody>
                              {k.idoszakok.map((i) => (
                                <IdoszakSor key={i.id} idoszak={i} szerkeszthet={canEdit} />
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}

      {canCreate && !urlap && (
        <button type="button" onClick={ujat} className="btn btn-primary mt-4">
          <Plus size={13} /> Új felvitele
        </button>
      )}

      {urlap && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busy ? undefined : bezar}>
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-[15px] font-medium text-text-primary">
              {szerkesztettId ? "Szerkesztés" : "Új felvitele"}
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label className="text-[11px] text-text-muted">Megnevezés *</label>
                <input value={urlap.nev} onChange={(e) => setUrlap({ ...urlap, nev: e.target.value })} className={inputClass} />
              </div>
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label className="text-[11px] text-text-muted">Csomag / részletek</label>
                <input value={urlap.csomag} onChange={(e) => setUrlap({ ...urlap, csomag: e.target.value })} className={inputClass} />
              </div>
              {tipusValaszthato && (
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] text-text-muted">Típus</label>
                  <select value={urlap.tipus} onChange={(e) => setUrlap({ ...urlap, tipus: e.target.value })} className={inputClass}>
                    {Object.entries(TIPUS_NEVEK).map(([ertek, nev]) => (
                      <option key={ertek} value={ertek}>
                        {nev}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Ciklus</label>
                <select value={urlap.ciklus} onChange={(e) => setUrlap({ ...urlap, ciklus: e.target.value })} className={inputClass}>
                  {Object.entries(CIKLUS_NEVEK).map(([ertek, nev]) => (
                    <option key={ertek} value={ertek}>
                      {nev}
                    </option>
                  ))}
                </select>
              </div>

              {/* A forduló kétféleképpen adható meg, és ez szándékos: a
                  visszatérőnél a MINTA a helyes ("minden hónap 7-én"), a
                  határozott idejűnél a konkrét dátum. */}
              {urlap.ciklus !== "egyszeri" && (
                <>
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-text-muted">Forduló napja (1-31)</label>
                    <input
                      type="number"
                      min={1}
                      max={31}
                      value={urlap.fordulo_nap}
                      onChange={(e) => setUrlap({ ...urlap, fordulo_nap: e.target.value })}
                      className={inputClass}
                    />
                  </div>
                  {urlap.ciklus === "eves" && (
                    <div className="flex flex-col gap-1">
                      <label className="text-[11px] text-text-muted">Forduló hónapja</label>
                      <select
                        value={urlap.fordulo_honap}
                        onChange={(e) => setUrlap({ ...urlap, fordulo_honap: e.target.value })}
                        className={inputClass}
                      >
                        <option value="">–</option>
                        {HONAP_NEVEK.map((nev, i) => (
                          <option key={nev} value={i + 1}>
                            {nev}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </>
              )}
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">
                  {urlap.ciklus === "egyszeri" ? "Lejárat *" : "Következő konkrét forduló"}
                </label>
                <input
                  type="date"
                  value={urlap.kovetkezo_fordulo}
                  onChange={(e) => setUrlap({ ...urlap, kovetkezo_fordulo: e.target.value })}
                  className={inputClass}
                />
                <p className="text-[11px] text-text-muted">
                  Ha ki van töltve, ez erősebb a mintánál – több évre előre kifizetett tételnél ezt használd.
                </p>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Ár (ciklusonként)</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={urlap.ar_osszeg}
                    onChange={(e) => setUrlap({ ...urlap, ar_osszeg: e.target.value })}
                    className={inputClass}
                  />
                  <select
                    value={urlap.ar_penznem}
                    onChange={(e) => setUrlap({ ...urlap, ar_penznem: e.target.value })}
                    className={`${inputClass} w-[90px]`}
                  >
                    {PENZNEMEK.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Felelős</label>
                <select
                  value={urlap.felelos_id}
                  onChange={(e) => setUrlap({ ...urlap, felelos_id: e.target.value })}
                  className={inputClass}
                >
                  <option value="">–</option>
                  {emberek.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.full_name}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-text-muted">Ő kapja az értesítést és a feladatot a fordulóról.</p>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Osztály</label>
                <input value={urlap.osztaly} onChange={(e) => setUrlap({ ...urlap, osztaly: e.target.value })} className={inputClass} />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Figyelmeztetés (nappal előbb)</label>
                <input
                  type="number"
                  min={0}
                  value={urlap.ertesites_napokkal}
                  onChange={(e) => setUrlap({ ...urlap, ertesites_napokkal: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Terhelt kártya</label>
                <input value={urlap.kartya} onChange={(e) => setUrlap({ ...urlap, kartya: e.target.value })} className={inputClass} />
              </div>
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label className="text-[11px] text-text-muted">Számla forrása (email, letöltő link)</label>
                <input
                  value={urlap.szamla_forras}
                  onChange={(e) => setUrlap({ ...urlap, szamla_forras: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label className="text-[11px] text-text-muted">Megjegyzés</label>
                <textarea
                  rows={3}
                  value={urlap.megjegyzes}
                  onChange={(e) => setUrlap({ ...urlap, megjegyzes: e.target.value })}
                  className={inputClass}
                />
              </div>
              <label className="flex items-center gap-2 text-[13px] text-text-primary sm:col-span-2">
                <input type="checkbox" checked={urlap.aktiv} onChange={(e) => setUrlap({ ...urlap, aktiv: e.target.checked })} />
                Aktív (a lejártáról figyelmeztessen)
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={bezar}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={ment}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Mentés…" : "Mentés"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
