"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderOpen, Paperclip } from "lucide-react";
import { ModalReteg } from "@/components/ModalReteg";
import { KuldesEllenorzo, type EllenorzoSor } from "@/components/KuldesEllenorzo";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import type { DocumentAttachment } from "@/lib/api";

/** Egy szerződésmódosítás sora (lásd backend routes/keret_modositasok.py). */
type Modositas = {
  id: number;
  keltezes: string | null;
  allapot: string | null;
  file_url: string | null;
  alairt_file_url: string | null;
  megbizas_targya: string | null;
  szerzodes_letrejotte: string | null;
  kikuldve: string | null;
  kikuldte: string | null;
};

function allapotTone(allapot: string | null): "success" | "warning" | "neutral" {
  if (allapot === "Kész") return "success";
  if (allapot === "Aláírásra vár") return "warning";
  return "neutral";
}

/** ALVÁLLALKOZÓI keretszerződés KEZELŐJE (a felhasználó kérése: legyen olyan
 * átlátható, mint a megrendelői keret) - egy helyen: a szerződés fájljai
 * (generált, aláírt és MINDEN további feltöltött fájl), a
 * szerződésmódosítások kiküldése/feltöltése és az aláírt példányok. */
export function AlvallalkozoiKeretKezelo({
  contractId,
  nev,
  email,
  szerzodesFileUrl,
  alairtFileUrl,
  cegNeve,
  szekhely,
  adoszam,
  kepviselo,
  nyilvantartasiSzam,
  megbizasTargya,
  szerzodesKelte,
  canCreate,
  canEdit,
  canDelete,
}: {
  contractId: number;
  nev: string;
  email: string | null;
  szerzodesFileUrl: string | null;
  alairtFileUrl: string | null;
  /** A szerződés cégadatai - a módosítás PILLANATKÉPKÉNT ezeket viszi a
   * papírra (lásd backend keret_modositas.uj_modositas), ezért a kiküldés
   * előtti ellenőrzőben pontosan ezeket mutatjuk (a felhasználó kérése). */
  cegNeve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  kepviselo: string | null;
  nyilvantartasiSzam: string | null;
  megbizasTargya: string | null;
  szerzodesKelte: string | null;
  canCreate: boolean;
  canEdit: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitva, setNyitva] = useState(false);
  const [modositasok, setModositasok] = useState<Modositas[] | null>(null);
  const [fajlok, setFajlok] = useState<DocumentAttachment[] | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Módosítás-kiküldő űrlap (a megrendelői keret mintájára): kísérőlevél +
  // a papírra kerülő három mező.
  const [kuldoNyitva, setKuldoNyitva] = useState(false);
  const [levelSzoveg, setLevelSzoveg] = useState("");
  const [keltezes, setKeltezes] = useState(() => new Date().toISOString().slice(0, 10));
  const [targy, setTargy] = useState("");
  const [letrejott, setLetrejott] = useState("");
  // Kiküldés előtti ELLENŐRZŐ (a felhasználó kérése): egyben minden adat,
  // amivel a módosítás kimegy - a tényleges küldés csak innen indul.
  const [ellenorzes, setEllenorzes] = useState(false);

  const betolt = useCallback(async () => {
    try {
      const [modRes, fajlRes] = await Promise.all([
        authFetch(`/api/v1/contracts/${contractId}/modositasok`),
        authFetch(`/api/v1/csatolmanyok/contract/${contractId}`),
      ]);
      if (!modRes.ok || !fajlRes.ok) {
        setHiba(`Nem sikerült betölteni (HTTP ${modRes.ok ? fajlRes.status : modRes.status}).`);
        return;
      }
      setModositasok((await modRes.json()) as Modositas[]);
      setFajlok((await fajlRes.json()) as DocumentAttachment[]);
      setHiba(null);
    } catch (err) {
      setHiba(`Nem sikerült betölteni: ${err}`);
    }
  }, [contractId]);

  useEffect(() => {
    if (!nyitva) return;
    // Adatbetöltés megnyitáskor - a szabály fals pozitívja.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void betolt();
  }, [nyitva, betolt]);

  async function muvelet(fut: () => Promise<Response>, hibaElotag: string) {
    setBusy(true);
    try {
      const res = await fut();
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`${hibaElotag}: ${detail?.detail ?? res.status}`);
        return false;
      }
      await betolt();
      router.refresh();
      return true;
    } catch (err) {
      alert(`${hibaElotag} (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  /** Amivel a papír TÉNYLEGESEN kimegy: az űrlap értéke, üresen a szerződésé
   * (ugyanaz a tartalék-lánc, mint a backend uj_modositas-ban). */
  function ellenorzoSorok(): EllenorzoSor[] {
    return [
      { cimke: "Cég neve", ertek: cegNeve || nev },
      { cimke: "Székhely", ertek: szekhely },
      { cimke: "Adószám", ertek: adoszam },
      { cimke: "Képviselő", ertek: kepviselo },
      { cimke: "Nyilvántartási szám", ertek: nyilvantartasiSzam },
      { cimke: "Megbízás tárgya", ertek: targy.trim() || megbizasTargya },
      { cimke: "Módosítás keltezése", ertek: keltezes },
      { cimke: "Eredeti szerződés kelte", ertek: letrejott || szerzodesKelte },
    ];
  }

  async function modositasKuldes() {
    setEllenorzes(false);
    const ok = await muvelet(
      () =>
        authFetch(`/api/v1/contracts/${contractId}/modositasok/generalas-es-kuldes`, {
          method: "POST",
          body: JSON.stringify({
            level_szoveg: levelSzoveg.trim() || null,
            keltezes: keltezes || null,
            megbizas_targya: targy.trim() || null,
            szerzodes_letrejotte: letrejott || null,
          }),
        }),
      "A módosítás kiküldése nem sikerült",
    );
    if (ok) {
      setKuldoNyitva(false);
      setLevelSzoveg("");
      setTargy("");
      setLetrejott("");
    }
  }

  function fajlFeltoltes(e: React.ChangeEvent<HTMLInputElement>, cel: (fajl: File) => Promise<Response>, hibaElotag: string) {
    const fajl = e.target.files?.[0];
    e.target.value = "";
    if (!fajl) return;
    void muvelet(() => cel(fajl), hibaElotag);
  }

  function multipart(url: string) {
    return (fajl: File) => {
      const fd = new FormData();
      fd.append("file", fajl);
      return authFetch(url, { method: "POST", body: fd });
    };
  }

  async function modositasTorles(m: Modositas) {
    if (!(await confirm("Biztosan törlöd ezt a szerződésmódosítást? A fájljai is törlődnek."))) return;
    void muvelet(
      () => authFetch(`/api/v1/contracts/${contractId}/modositasok/${m.id}`, { method: "DELETE" }),
      "A törlés nem sikerült",
    );
  }

  return (
    <span onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className="inline-flex items-center gap-1 text-[12.5px] text-text-accent hover:underline"
      >
        <FolderOpen size={12} aria-hidden /> Kezelés
      </button>
      {nyitva && (
        <ModalReteg onClose={() => setNyitva(false)}>
          <div
            role="dialog"
            aria-modal="true"
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 text-left shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-[15px] font-medium text-text-primary">{nev} – keretszerződés</h3>
            <p className="mb-4 mt-0.5 text-[12.5px] text-text-muted">
              {email ? `A papírok ide mennek: ${email}` : "Nincs e-mail cím a szerződésen."}
            </p>
            {hiba && <p className="mb-3 text-[13px] text-text-danger">{hiba}</p>}

            {/* ── Fájlok: a generált és aláírt példány + MINDEN feltöltött fájl ── */}
            <h4 className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">Fájlok</h4>
            <ul className="space-y-1.5 text-[13px]">
              {szerzodesFileUrl && (
                <li className="flex items-center gap-1.5">
                  <Paperclip size={13} className="shrink-0 text-text-muted" />
                  <a href={szerzodesFileUrl} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                    Keretszerződés (kiküldött példány)
                  </a>
                </li>
              )}
              {alairtFileUrl && (
                <li className="flex items-center gap-1.5">
                  <Paperclip size={13} className="shrink-0 text-text-muted" />
                  <a href={alairtFileUrl} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                    Aláírt keretszerződés
                  </a>
                  <StatusBadge label="Aláírva" tone="success" />
                </li>
              )}
              {(fajlok ?? []).map((f) => (
                <li key={f.id} className="flex items-center gap-1.5">
                  <Paperclip size={13} className="shrink-0 text-text-muted" />
                  <a href={f.url} target="_blank" rel="noopener noreferrer" className="truncate text-text-accent hover:underline">
                    {f.filename}
                  </a>
                </li>
              ))}
              {!szerzodesFileUrl && !alairtFileUrl && (fajlok?.length ?? 0) === 0 && (
                <li className="text-text-muted">Még nincs fájl ehhez a keretszerződéshez.</li>
              )}
            </ul>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-[12.5px]">
              {canEdit && (
                <label className="cursor-pointer text-text-secondary hover:underline">
                  + Aláírt keretszerződés feltöltése
                  <input
                    type="file"
                    className="hidden"
                    disabled={busy}
                    onChange={(e) =>
                      fajlFeltoltes(e, multipart(`/api/v1/contracts/${contractId}/alairt-fajl`), "A feltöltés nem sikerült")
                    }
                  />
                </label>
              )}
              {canEdit && (
                <label className="cursor-pointer text-text-secondary hover:underline">
                  + Egyéb fájl feltöltése
                  <input
                    type="file"
                    className="hidden"
                    disabled={busy}
                    onChange={(e) =>
                      fajlFeltoltes(
                        e,
                        multipart(`/api/v1/csatolmanyok/contract/${contractId}?kategoria=szerzodes`),
                        "A feltöltés nem sikerült",
                      )
                    }
                  />
                </label>
              )}
            </div>

            {/* ── Szerződésmódosítások (a megrendelői keret mintájára) ── */}
            <h4 className="mb-1.5 mt-5 text-[12px] font-medium uppercase tracking-wide text-text-muted">
              Szerződésmódosítások
            </h4>
            {modositasok === null ? (
              <p className="text-[13px] text-text-muted">Betöltés…</p>
            ) : modositasok.length === 0 ? (
              <p className="text-[13px] text-text-muted">Még nincs szerződésmódosítás.</p>
            ) : (
              <ul className="space-y-2">
                {modositasok.map((m) => (
                  <li key={m.id} className="rounded-[var(--radius)] border border-border p-2.5 text-[13px]">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-text-primary">
                        Módosítás – {m.keltezes ?? "nincs keltezés"}
                        {m.kikuldte && <span className="text-text-muted"> · küldte: {m.kikuldte}</span>}
                      </span>
                      <StatusBadge label={m.allapot ?? "Készítés alatt"} tone={allapotTone(m.allapot)} />
                    </div>
                    {m.megbizas_targya && <p className="mt-0.5 text-[12px] text-text-muted">{m.megbizas_targya}</p>}
                    <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[12.5px]">
                      {m.file_url && (
                        <a href={m.file_url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                          Dokumentum
                        </a>
                      )}
                      {m.alairt_file_url && (
                        <a href={m.alairt_file_url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                          Aláírt példány
                        </a>
                      )}
                      {canEdit && !m.alairt_file_url && (
                        <label className="cursor-pointer text-text-secondary hover:underline">
                          + Aláírt példány feltöltése
                          <input
                            type="file"
                            className="hidden"
                            disabled={busy}
                            onChange={(e) =>
                              fajlFeltoltes(
                                e,
                                multipart(`/api/v1/contracts/${contractId}/modositasok/${m.id}/alairt-fajl`),
                                "A feltöltés nem sikerült",
                              )
                            }
                          />
                        </label>
                      )}
                      {canDelete && (
                        <button type="button" onClick={() => void modositasTorles(m)} disabled={busy} className="text-text-danger hover:underline disabled:opacity-50">
                          Törlés
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-2 flex flex-wrap items-center gap-3 text-[12.5px]">
              {canCreate && (
                <button
                  type="button"
                  onClick={() => setKuldoNyitva((n) => !n)}
                  disabled={busy}
                  className="text-text-secondary hover:underline disabled:opacity-50"
                >
                  + Módosítás kiküldése
                </button>
              )}
              {canCreate && (
                <label className="cursor-pointer text-text-secondary hover:underline">
                  + Saját módosítás feltöltése
                  <input
                    type="file"
                    className="hidden"
                    disabled={busy}
                    onChange={(e) =>
                      fajlFeltoltes(
                        e,
                        multipart(`/api/v1/contracts/${contractId}/modositasok/sajat-fajl`),
                        "A feltöltés nem sikerült",
                      )
                    }
                  />
                </label>
              )}
            </div>

            {/* A kiküldő űrlap: kísérőlevél + a papírra kerülő mezők. A
                dokumentum a sablonból generálódik és e-mailben megy ki. */}
            {kuldoNyitva && (
              <div className="mt-3 space-y-2 rounded-[var(--radius)] border border-border bg-surface-3 p-3 text-[13px]">
                <p className="text-[12px] text-text-muted">
                  A módosítás a sablonból generálódik és e-mailben kimegy{email ? ` ide: ${email}` : ""}. A kísérőlevél
                  végére a küldő fiók aláírása kerül.
                </p>
                <textarea
                  value={levelSzoveg}
                  onChange={(e) => setLevelSzoveg(e.target.value)}
                  placeholder="Kísérőlevél szövege (üresen az alapszöveg megy)"
                  rows={3}
                  className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-2 text-[13px] text-text-primary focus:outline-none"
                />
                <div className="flex flex-wrap gap-3">
                  <label className="flex items-center gap-1.5 text-[12.5px] text-text-secondary">
                    Keltezés
                    <input type="date" value={keltezes} onChange={(e) => setKeltezes(e.target.value)} className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-text-primary" />
                  </label>
                  <label className="flex items-center gap-1.5 text-[12.5px] text-text-secondary">
                    Eredeti szerződés kelte
                    <input type="date" value={letrejott} onChange={(e) => setLetrejott(e.target.value)} className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-text-primary" />
                  </label>
                </div>
                <input
                  value={targy}
                  onChange={(e) => setTargy(e.target.value)}
                  placeholder="Megbízás tárgya (üresen a szerződésé)"
                  className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
                />
                <div className="flex items-center gap-2">
                  {/* Nem küld azonnal: előbb az ellenőrző mutatja egyben az
                      összes adatot, amivel a papír kimegy (a felhasználó
                      kérése). */}
                  <button type="button" onClick={() => setEllenorzes(true)} disabled={busy} className="btn btn-primary disabled:opacity-50">
                    {busy ? "Küldés…" : "Generálás és kiküldés"}
                  </button>
                  <button type="button" onClick={() => setKuldoNyitva(false)} className="text-[12.5px] text-text-secondary hover:underline">
                    Mégse
                  </button>
                </div>
              </div>
            )}
          </div>
        </ModalReteg>
      )}
      {ellenorzes && (
        <KuldesEllenorzo
          cim="Szerződésmódosítás kiküldése"
          bevezeto="A módosítás ezekkel az adatokkal generálódik a sablonból, és azonnal ki is megy e-mailben. Ellenőrizd, mielőtt elindítod."
          cimzett={email}
          sorok={ellenorzoSorok()}
          gombCimke="Kiküldés"
          onMegse={() => setEllenorzes(false)}
          onKuld={() => void modositasKuldes()}
        >
          <p className="text-[12.5px] text-text-secondary">
            Kísérőlevél: {levelSzoveg.trim() ? `„${levelSzoveg.trim()}”` : "az alapszöveg megy"} - a végére a küldő
            fiók aláírása kerül.
          </p>
        </KuldesEllenorzo>
      )}
    </span>
  );
}
