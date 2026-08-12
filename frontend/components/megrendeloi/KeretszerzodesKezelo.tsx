"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { KeretszerzodesModal } from "@/components/megrendeloi/KeretszerzodesModal";
import { KuldesEllenorzo, type EllenorzoSor } from "@/components/KuldesEllenorzo";
import { SajatPapirFeltoltes } from "@/components/SajatPapirFeltoltes";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";
import { authFetch } from "@/lib/authFetch";
// A dátumformázó a lib/utokovetes-ből jön, NEM a lib/api-ból: az utóbbi a
// `next/headers`-t is behúzná a böngésző-csomagba, és eltörné a buildet (a
// típus import viszont fordításkor eltűnik, az rendben van).
import { datum } from "@/lib/utokovetes";
import type { MegrendeloiKeret } from "@/lib/api";

type Urlap = {
  ceg_neve: string;
  szekhely: string;
  adoszam: string;
  kepviselo: string;
  nyilvantartasi_szam: string;
  email: string;
  megbizas_targya: string;
  keltezes: string;
};

const URES: Urlap = {
  ceg_neve: "",
  szekhely: "",
  adoszam: "",
  kepviselo: "",
  nyilvantartasi_szam: "",
  email: "",
  megbizas_targya: "",
  keltezes: "",
};

function urlapKeretbol(k: MegrendeloiKeret): Urlap {
  return {
    ceg_neve: k.ceg_neve ?? k.client_nev ?? "",
    szekhely: k.szekhely ?? "",
    adoszam: k.adoszam ?? "",
    kepviselo: k.kepviselo ?? "",
    nyilvantartasi_szam: k.nyilvantartasi_szam ?? "",
    email: k.email ?? "",
    megbizas_targya: k.megbizas_targya ?? "",
    keltezes: k.keltezes ?? "",
  };
}

/** Megrendelői keretszerződések - akikkel KERETBEN dolgozunk.
 *
 * Az adat nagy része már megvolt: a Notion "Keretszerződés" adatbázisa a
 * `Contract` táblába importálódik (lásd backend
 * routes/megrendeloi_keretszerzodesek.py) - ez az oldal azt adja hozzá, hogy
 * lehessen újat készíteni, kiküldeni, és a saját/aláírt példányt feltölteni.
 *
 * Az ÉLŐ keretszerződés kiváltja az eseti szerződést, a teljesítési igazolást
 * viszont NEM: a keret arról szól, milyen feltételekkel dolgozunk együtt, a
 * TIG arról, hogy egy konkrét munka elkészült. */
export function KeretszerzodesKezelo({
  keretek,
  canCreate,
  canEdit,
  canDelete,
}: {
  keretek: MegrendeloiKeret[];
  canCreate: boolean;
  canEdit: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const [nyitva, setNyitva] = useState(false);
  const [szerkesztett, setSzerkesztett] = useState<MegrendeloiKeret | null>(null);
  const [urlap, setUrlap] = useState<Urlap>(URES);
  const [busy, setBusy] = useState(false);
  const [kuldendo, setKuldendo] = useState<MegrendeloiKeret | null>(null);
  const [nyitottKeret, setNyitottKeret] = useState<number | null>(null);

  function frissit<K extends keyof Urlap>(kulcs: K, ertek: Urlap[K]) {
    setUrlap((elozo) => ({ ...elozo, [kulcs]: ertek }));
  }

  function ujat() {
    setSzerkesztett(null);
    setUrlap(URES);
    setNyitva(true);
  }

  function szerkeszt(k: MegrendeloiKeret) {
    setSzerkesztett(k);
    setUrlap(urlapKeretbol(k));
    setNyitva(true);
  }

  function bezar() {
    setNyitva(false);
    setSzerkesztett(null);
    setUrlap(URES);
  }

  async function ment() {
    if (!urlap.ceg_neve.trim()) {
      toast("Add meg a cég nevét.");
      return;
    }
    setBusy(true);
    try {
      const torzs = {
        ceg_neve: urlap.ceg_neve || null,
        szekhely: urlap.szekhely || null,
        adoszam: urlap.adoszam || null,
        kepviselo: urlap.kepviselo || null,
        nyilvantartasi_szam: urlap.nyilvantartasi_szam || null,
        email: urlap.email || null,
        megbizas_targya: urlap.megbizas_targya || null,
        keltezes: urlap.keltezes || null,
      };
      const res = await authFetch(
        szerkesztett
          ? `/api/v1/megrendeloi-keretszerzodesek/${szerkesztett.id}`
          : "/api/v1/megrendeloi-keretszerzodesek",
        { method: szerkesztett ? "PATCH" : "POST", body: JSON.stringify(torzs) },
      );
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen mentés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      bezar();
      router.refresh();
    } catch (err) {
      toast(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  function ellenorzoSorok(k: MegrendeloiKeret): EllenorzoSor[] {
    return [
      { cimke: "Cég neve", ertek: k.ceg_neve ?? k.client_nev },
      { cimke: "Székhely", ertek: k.szekhely },
      { cimke: "Adószám", ertek: k.adoszam },
      { cimke: "Képviselő", ertek: k.kepviselo },
      { cimke: "Nyilvántartási szám", ertek: k.nyilvantartasi_szam },
      { cimke: "Megbízás tárgya", ertek: k.megbizas_targya },
      { cimke: "Keltezés", ertek: k.keltezes },
    ];
  }

  async function kuldes(k: MegrendeloiKeret) {
    setKuldendo(null);
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/megrendeloi-keretszerzodesek/${k.id}/generalas-es-kuldes`, {
        method: "POST",
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen küldés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      toast(`Sikertelen küldés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function alairtFeltoltes(keretId: number, file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await authFetch(`/api/v1/megrendeloi-keretszerzodesek/${keretId}/alairt-fajl`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen feltöltés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      toast(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    }
  }

  /** A törlés LEOLDJA a projektkódokat, amitől azoknak megint kell szerződés -
   * ezt előre kimondjuk, mert ez a művelet lényege, nem a mellékhatása. */
  async function torles(k: MegrendeloiKeret) {
    const nev = k.ceg_neve ?? k.client_nev ?? `#${k.id}`;
    const kovetkezmeny =
      k.projektkod_db > 0
        ? ` A hozzá tartozó ${k.projektkod_db} projektkód leoldódik róla, és onnantól megint kell nekik megrendelői szerződés.`
        : "";
    if (!(await confirm(`Biztosan törlöd a(z) "${nev}" keretszerződését?${kovetkezmeny}`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/megrendeloi-keretszerzodesek/${k.id}`, { method: "DELETE" });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen törlés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      const eredmeny = await res.json().catch(() => null);
      if (eredmeny?.leoldott_projektkod) {
        const ujra = eredmeny.ujranyitott_papir
          ? `, ${eredmeny.ujranyitott_papir} korábban kihagyott szerződés újranyílt`
          : "";
        toast(`Törölve. ${eredmeny.leoldott_projektkod} projektkódnak megint kell szerződés${ujra}.`);
      }
      router.refresh();
    } catch (err) {
      toast(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 text-[13px]">
      {canCreate && (
        <button
          type="button"
          onClick={ujat}
          disabled={busy}
          className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90 disabled:opacity-50"
        >
          + Új keretszerződés
        </button>
      )}

      {keretek.length === 0 ? (
        <p className="text-text-muted">Még nincs megrendelői keretszerződés.</p>
      ) : (
        <ul className="space-y-2">
          {keretek.map((k) => (
            <li key={k.id} className="rounded-[var(--radius)] border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setNyitottKeret(k.id)}
                  className="text-left text-[14px] text-text-primary hover:text-text-accent hover:underline"
                >
                  {k.ceg_neve ?? k.client_nev ?? `#${k.id}`}
                </button>
                <span className="flex items-center gap-2">
                  {k.ervenyes ? (
                    <StatusBadge label="Élő keret" tone="success" />
                  ) : (
                    <StatusBadge label="Nem élő" tone="neutral" />
                  )}
                  {k.alairva ? (
                    <StatusBadge label="Aláírva" tone="success" />
                  ) : k.allapot === "Kiküldve" ? (
                    <StatusBadge label="Kiküldve, aláírásra vár" tone="warning" />
                  ) : (
                    <StatusBadge label={k.allapot ?? "Készítés alatt"} tone="warning" />
                  )}
                </span>
              </div>
              <p className="mt-1 text-text-muted">
                {[k.adoszam, k.szekhely, k.email].filter(Boolean).join(" · ") || "Nincs cégadat rögzítve"}
              </p>
              <p className="mt-0.5 text-text-muted">
                Keltezés: {datum(k.keltezes)} ·{" "}
                {k.projektkod_db > 0 ? `${k.projektkod_db} projektkódnál használjuk` : "Még nincs hozzá projektkód"}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => setNyitottKeret(k.id)}
                  className="text-text-accent hover:underline"
                >
                  Megnyitás
                </button>
                {k.file_url && (
                  <a href={k.file_url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                    Keretszerződés megnyitása
                  </a>
                )}
                {k.alairt_file_url && (
                  <a
                    href={k.alairt_file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-accent hover:underline"
                  >
                    Aláírt példány
                  </a>
                )}
                {canEdit && (
                  <button type="button" onClick={() => szerkeszt(k)} disabled={busy} className="text-text-secondary hover:underline disabled:opacity-50">
                    Szerkesztés
                  </button>
                )}
                {canCreate && (
                  <button
                    type="button"
                    onClick={() => setKuldendo(k)}
                    disabled={busy}
                    className="text-text-secondary hover:underline disabled:opacity-50"
                  >
                    Generálás és küldés
                  </button>
                )}
                {/* Saját sablonnal készült vagy még a rendszer előtti papír. */}
                {canEdit && (
                  <SajatPapirFeltoltes
                    cimke="Saját keretszerződés feltöltése"
                    feltoltesPath={`/api/v1/megrendeloi-keretszerzodesek/${k.id}/sajat-fajl`}
                    disabled={busy}
                    onKesz={() => router.refresh()}
                  />
                )}
                {canEdit && !k.alairt_file_url && (
                  <label className="cursor-pointer text-text-secondary hover:underline">
                    + Aláírt példány feltöltése
                    <input
                      type="file"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) alairtFeltoltes(k.id, file);
                        e.target.value = "";
                      }}
                    />
                  </label>
                )}
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => torles(k)}
                    disabled={busy}
                    className="text-text-danger hover:underline disabled:opacity-50"
                  >
                    Törlés
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {nyitva && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busy ? undefined : bezar}>
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-[15px] font-medium text-text-primary">
              {szerkesztett ? "Keretszerződés szerkesztése" : "Új megrendelői keretszerződés"}
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Mezo label="Cég neve *">
                <input value={urlap.ceg_neve} onChange={(e) => frissit("ceg_neve", e.target.value)} disabled={busy} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Székhely">
                <input value={urlap.szekhely} onChange={(e) => frissit("szekhely", e.target.value)} disabled={busy} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Adószám">
                <input value={urlap.adoszam} onChange={(e) => frissit("adoszam", e.target.value)} disabled={busy} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Képviselő">
                <input value={urlap.kepviselo} onChange={(e) => frissit("kepviselo", e.target.value)} disabled={busy} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Nyilvántartási szám">
                <input
                  value={urlap.nyilvantartasi_szam}
                  onChange={(e) => frissit("nyilvantartasi_szam", e.target.value)}
                  disabled={busy}
                  className={mezoOsztaly}
                />
              </Mezo>
              <Mezo label="E-mail cím (ide megy a papír)">
                <input value={urlap.email} onChange={(e) => frissit("email", e.target.value)} disabled={busy} className={mezoOsztaly} />
              </Mezo>
              <Mezo label="Megbízás tárgya">
                <input
                  value={urlap.megbizas_targya}
                  onChange={(e) => frissit("megbizas_targya", e.target.value)}
                  disabled={busy}
                  className={mezoOsztaly}
                />
              </Mezo>
              <Mezo label="Keltezés dátuma">
                <input
                  type="date"
                  value={urlap.keltezes}
                  onChange={(e) => frissit("keltezes", e.target.value)}
                  disabled={busy}
                  className={mezoOsztaly}
                />
              </Mezo>
            </div>
            <div className="mt-5 flex justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={bezar}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={ment}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Mentés…" : "Mentés"}
              </button>
            </div>
          </div>
        </div>
      )}

      {nyitottKeret !== null && (
        <KeretszerzodesModal keretId={nyitottKeret} onClose={() => setNyitottKeret(null)} />
      )}

      {kuldendo && (
        <KuldesEllenorzo
          cim="Keretszerződés kiküldése"
          bevezeto="A dokumentum ezekkel az adatokkal generálódik, és azonnal ki is megy e-mailben."
          cimzett={kuldendo.email}
          sorok={ellenorzoSorok(kuldendo)}
          gombCimke="Generálás és küldés"
          onMegse={() => setKuldendo(null)}
          onKuld={() => kuldes(kuldendo)}
        />
      )}
    </div>
  );
}

const mezoOsztaly =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

function Mezo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] text-text-muted">{label}</label>
      {children}
    </div>
  );
}
