"use client";

import { Fragment, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Paperclip, Plus, Trash2, Upload } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { ModalReteg } from "@/components/ModalReteg";
import { PapirFeltoltes } from "@/components/kotelezettseg/PapirFeltoltes";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { huDatum } from "@/lib/huDate";
import { formatHuf } from "@/lib/penz";
import type { Kotelezettseg, KotelezettsegIdoszak } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

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

/** Ugyanaz a szókészlet, mint a Pénzügy kiadásainál - így a kimutatás egyben
 * látja az itt és az ott rögzített fizetéseket. */
const FIZETESI_MODOK = ["Átutalás", "Készpénz", "Bankkártya"];

/** Bruttó a nettóból. Ha nincs áfa, a kettő ugyanaz - ugyanaz a szabály, mint
 * a backendben (routes/kotelezettsegek.brutto). */
function bruttoBol(netto: number | null, pluszAfa: boolean): number | null {
  if (netto == null || Number.isNaN(netto)) return null;
  return pluszAfa ? Math.round(netto * 1.27 * 100) / 100 : netto;
}

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
  if (k.kovetkezo_fordulo) return huDatum(k.kovetkezo_fordulo);
  // Dátum nélküli, a Google-táblázatból importált sor: ott csak a minta van.
  if (k.ciklus === "havi") return k.fordulo_nap ? `minden hónap ${k.fordulo_nap}.` : "–";
  if (k.fordulo_honap && k.fordulo_nap) return `minden ${HONAP_NEVEK[k.fordulo_honap - 1]} ${k.fordulo_nap}.`;
  return "–";
}

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

type UrlapAllapot = {
  nev: string;
  csomag: string;
  tipus: string;
  ciklus: string;
  /** A forduló EGYETLEN mezője: egy konkrét dátum. A nap és a hónap benne
   * van - külön mezőben csak ugyanazt kérdeznénk még egyszer. */
  kovetkezo_fordulo: string;
  felelos_id: string;
  aktiv: boolean;
  fizetesi_mod: string;
  /** NETTÓ ár; a bruttó ebből és az áfa-kapcsolóból jön. */
  ar_osszeg: string;
  ar_plusz_afa: boolean;
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
    kovetkezo_fordulo: "",
    felelos_id: "",
    aktiv: true,
    fizetesi_mod: "",
    ar_osszeg: "",
    ar_plusz_afa: false,
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
    // A Google-táblázatból importált soroknál nincs konkrét dátum, csak minta
    // ("minden hónap 13."). Az űrlap a KISZÁMOLT következő fordulóval nyílik,
    // különben a mentés dátum nélkül maradna.
    kovetkezo_fordulo: k.kovetkezo_fordulo ?? k.kovetkezo_esedekesseg ?? "",
    felelos_id: k.felelos_id != null ? String(k.felelos_id) : "",
    aktiv: k.aktiv,
    fizetesi_mod: k.fizetesi_mod ?? "",
    ar_osszeg: k.ar_osszeg != null ? String(k.ar_osszeg) : "",
    ar_plusz_afa: k.ar_plusz_afa,
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
  const confirm = useConfirm();
  const [osszeg, setOsszeg] = useState(idoszak.osszeg != null ? String(idoszak.osszeg) : "");
  const [pluszAfa, setPluszAfa] = useState(idoszak.plusz_afa);
  const [hufOsszeg, setHufOsszeg] = useState(idoszak.huf_osszeg != null ? String(idoszak.huf_osszeg) : "");
  const [busy, setBusy] = useState(false);
  const [feltolt, setFeltolt] = useState(false);

  async function ment(afa: boolean = pluszAfa) {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/kotelezettsegek/idoszakok/${idoszak.id}`, {
        method: "PUT",
        body: JSON.stringify({
          osszeg: osszeg.trim() ? Number(osszeg) : null,
          plusz_afa: afa,
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

  async function szamlaTorles(fajl: { id: number; filename: string }) {
    if (!(await confirm(`Törlöd ezt a fájlt: "${fajl.filename}"?`))) return;
    setFeltolt(true);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${fajl.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setFeltolt(false);
    }
  }

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 pr-4 whitespace-nowrap text-text-primary">{huDatum(idoszak.esedekesseg)}</td>
      <td className="py-2 pr-4">
        {szerkeszthet ? (
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={osszeg}
              onChange={(e) => setOsszeg(e.target.value)}
              onBlur={() => ment()}
              disabled={busy}
              placeholder="Nettó"
              className={`${inputClass} w-[120px]`}
            />
            {/* Az áfa-kapcsoló azonnal ment: a bruttó ebből számolódik, és a
                felhasználó a következő pillanatban azt akarja látni. */}
            <label className="flex items-center gap-1 whitespace-nowrap text-[12px] text-text-secondary">
              <input
                type="checkbox"
                checked={pluszAfa}
                disabled={busy}
                onChange={(e) => {
                  setPluszAfa(e.target.checked);
                  ment(e.target.checked);
                }}
              />
              + ÁFA
            </label>
          </div>
        ) : (
          <>
            {penzzel(idoszak.osszeg, idoszak.penznem)}
            {idoszak.plusz_afa && <span className="ml-1 text-[11px] text-text-muted">+ ÁFA</span>}
          </>
        )}
      </td>
      <td className="py-2 pr-4 whitespace-nowrap text-text-secondary">
        {penzzel(bruttoBol(idoszak.osszeg, idoszak.plusz_afa), idoszak.penznem)}
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
              onBlur={() => ment()}
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
        {/* Korábban csak a DARABSZÁM látszott: a feltöltött számlát megnyitni
            vagy törölni nem lehetett. Most maguk a fájlok állnak itt, és a
            feltöltés gomb - nem link-stílusú szöveg, amit URL-beírásnak lehet
            olvasni. */}
        {idoszak.szamlak.length === 0 ? (
          <span className="text-text-muted">nincs</span>
        ) : (
          <ul className="space-y-1">
            {idoszak.szamlak.map((f) => (
              <li key={f.id} className="flex items-center gap-1.5">
                <Paperclip size={11} className="shrink-0 text-text-muted" />
                <a
                  href={f.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="max-w-[180px] truncate text-text-accent hover:underline"
                  title={f.filename}
                >
                  {f.filename}
                </a>
                {szerkeszthet && (
                  <button
                    type="button"
                    onClick={() => szamlaTorles(f)}
                    disabled={feltolt}
                    title="Fájl törlése"
                    className="rounded-[var(--radius)] p-0.5 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                  >
                    <Trash2 size={11} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {szerkeszthet && (
          <label
            className={`mt-1 inline-flex w-fit items-center gap-1.5 rounded-[var(--radius)] border border-border px-2 py-0.5 text-[12px] text-text-secondary ${
              feltolt ? "opacity-50" : "cursor-pointer hover:bg-surface-3"
            }`}
          >
            <Upload size={11} />
            {feltolt ? "Feltöltés…" : "Számla feltöltése (PDF, fotó)"}
            <input
              type="file"
              multiple
              accept="application/pdf,image/*"
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
    if (!urlap.kovetkezo_fordulo) {
      alert("Add meg a következő forduló (lejárat) dátumát.");
      return;
    }
    setBusy(true);
    try {
      const test = {
        nev: urlap.nev.trim(),
        csomag: urlap.csomag.trim() || null,
        tipus: urlap.tipus,
        ciklus: urlap.ciklus,
        kovetkezo_fordulo: urlap.kovetkezo_fordulo || null,
        felelos_id: urlap.felelos_id ? Number(urlap.felelos_id) : null,
        auto_id: autoId ?? null,
        aktiv: urlap.aktiv,
        fizetesi_mod: urlap.fizetesi_mod || null,
        ar_osszeg: urlap.ar_osszeg.trim() ? Number(urlap.ar_osszeg) : null,
        ar_plusz_afa: urlap.ar_plusz_afa,
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
        <div className="overflow-x-auto">
        <table className="os-table min-w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Megnevezés</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Forduló</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Következő</th>
              <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Nettó ár</th>
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
                      {k.ar_plusz_afa && (
                        <span className="block text-[11px] text-text-muted">
                          + ÁFA → {penzzel(k.ar_brutto, k.ar_penznem)}
                        </span>
                      )}
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
                          {k.fizetesi_mod && (
                            <p>
                              Fizetés módja: <span className="text-text-secondary">{k.fizetesi_mod}</span>
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

                        {/* A kötelezettséghez MAGÁHOZ tartozó papírok: kötvény,
                            szerződés, a forgalmi másolata. A fordulónkénti
                            számla ettől külön, lent, az adott fordulónál van. */}
                        <p className="t-label mb-1.5">Dokumentumok (kötvény, szerződés, bármi)</p>
                        <div className="mb-4">
                          <PapirFeltoltes
                            entityType="kotelezettseg"
                            entityId={k.id}
                            canEdit={canEdit}
                            canDelete={canDelete}
                          />
                        </div>

                        <p className="t-label mb-1.5">Fordulók – mennyibe került, és hol a számla</p>
                        {k.idoszakok.length === 0 ? (
                          <p className="text-[12.5px] text-text-muted">
                            Még nincs esedékes forduló. Az első fordulónál magától megjelenik itt egy sor.
                          </p>
                        ) : (
                          <div className="overflow-x-auto">
                          <table className="os-table min-w-full border-collapse text-[12.5px]">
                            <thead>
                              <tr className="border-b border-border">
                                <th className="py-1 pr-4 text-left font-medium text-text-muted">Forduló</th>
                                <th className="py-1 pr-4 text-left font-medium text-text-muted">Nettó</th>
                                <th className="py-1 pr-4 text-left font-medium text-text-muted">Bruttó</th>
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
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        </div>
      )}

      {canCreate && !urlap && (
        <button type="button" onClick={ujat} className="btn btn-primary mt-4">
          <Plus size={13} /> Új felvitele
        </button>
      )}

      {urlap && (
        <ModalReteg onClose={busy ? undefined : bezar}>
          <div
            className="my-auto w-full max-w-2xl rounded-[var(--radius)] border border-border bg-surface-2 p-6"
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
                  <KeresosSelect
                    value={urlap.tipus}
                    options={Object.entries(TIPUS_NEVEK).map(([ertek, nev]) => ({ value: ertek, label: nev }))}
                    onChange={(ertek) => setUrlap({ ...urlap, tipus: ertek })}
                  />
                </div>
              )}
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Ciklus</label>
                <KeresosSelect
                  value={urlap.ciklus}
                  options={Object.entries(CIKLUS_NEVEK).map(([ertek, nev]) => ({ value: ertek, label: nev }))}
                  onChange={(ertek) => setUrlap({ ...urlap, ciklus: ertek })}
                />
              </div>

              {/* A forduló EGY dátum: a nap és a hónap benne van, a ciklus
                  pedig megmondja, mennyivel lép tovább (havi egy hónapot, éves
                  egy évet) - lásd backend services/kotelezettseg.py. */}
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label className="text-[11px] text-text-muted">
                  {urlap.ciklus === "egyszeri" ? "Lejárat *" : "Következő forduló *"}
                </label>
                <input
                  type="date"
                  value={urlap.kovetkezo_fordulo}
                  onChange={(e) => setUrlap({ ...urlap, kovetkezo_fordulo: e.target.value })}
                  className={inputClass}
                />
                <p className="text-[11px] text-text-muted">
                  {urlap.ciklus === "egyszeri"
                    ? "Ekkor jár le – magától nem újul meg."
                    : "Innentől a ciklus lépteti tovább. Több évre előre kifizetett tételnél a tényleges lejáratot add meg."}
                </p>
              </div>

              {/* Az ár NETTÓBAN, mellette az áfa-kapcsoló: a bruttót ebből
                  számoljuk, nem külön mezőben tároljuk. */}
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Nettó ár (ciklusonként)</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={urlap.ar_osszeg}
                    onChange={(e) => setUrlap({ ...urlap, ar_osszeg: e.target.value })}
                    className={inputClass}
                  />
                  <KeresosSelect
                    value={urlap.ar_penznem}
                    options={PENZNEMEK.map((p) => ({ value: p, label: p }))}
                    onChange={(ertek) => setUrlap({ ...urlap, ar_penznem: ertek })}
                    className="w-[90px]"
                  />
                </div>
                <label className="mt-1 flex items-center gap-2 text-[12.5px] text-text-primary">
                  <input
                    type="checkbox"
                    checked={urlap.ar_plusz_afa}
                    onChange={(e) => setUrlap({ ...urlap, ar_plusz_afa: e.target.checked })}
                  />
                  Plusz ÁFA
                </label>
                <p className="text-[11px] text-text-muted">
                  Bruttó:{" "}
                  {urlap.ar_osszeg.trim()
                    ? penzzel(bruttoBol(Number(urlap.ar_osszeg), urlap.ar_plusz_afa), urlap.ar_penznem)
                    : "–"}
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Hogyan fizetjük</label>
                <KeresosSelect
                  value={urlap.fizetesi_mod || null}
                  options={FIZETESI_MODOK.map((m) => ({ value: m, label: m }))}
                  onChange={(ertek) => setUrlap({ ...urlap, fizetesi_mod: ertek })}
                  placeholder="–"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Felelős</label>
                <KeresosSelect
                  value={urlap.felelos_id || null}
                  options={emberek.map((e) => ({ value: String(e.id), label: e.full_name }))}
                  onChange={(ertek) => setUrlap({ ...urlap, felelos_id: ertek })}
                  placeholder="–"
                />
                <p className="text-[11px] text-text-muted">Ő kapja az értesítést és a feladatot a fordulóról.</p>
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
        </ModalReteg>
      )}
    </div>
  );
}
