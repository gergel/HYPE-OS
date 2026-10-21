"use client";

import { useMemo, useState } from "react";
import { authFetch } from "@/lib/authFetch";
import type { Arajanlat, ArajanlatTetel } from "@/lib/api";
import {
  ArajanlatAdat,
  ArajanlatBlokk,
  ArajanlatSzekcio,
  ArajanlatTetelSor,
  BRAND_BEALLITAS,
  ajanlatAdatBetoltes,
  blokkOsszeg,
  osszegSzoveg,
  osszesites,
  szamErtek,
  szekcioOsszeg,
  tetelOsszeg,
  ujId,
  uresAjanlat,
  uresBlokk,
  uresSzekcio,
  uresTetel,
} from "@/components/arajanlat/arajanlatTipusok";

/** Az árajánlat-szerkesztő: a feltöltött papír-sablon hű mása, React
 * állapotból - blokkok > szekciók > tételek, kedvezmény, ÁFA-kapcsoló,
 * HYPE/ContentBee logó-váltó, katalógusból tétel-hozzáadás, mentés
 * ajánlatként vagy sablonként, és PDF (nyomtatás).
 *
 * A LAP SZÁNDÉKOSAN mindig világos, a témától függetlenül: papírt utánoz,
 * és nyomtatásban is pontosan így néz ki. A nyomtatás a visibility-trükkel
 * csak a lapot viszi papírra (lásd a lenti <style> print-blokkját). */
export function ArajanlatSzerkeszto({
  mentett,
  katalogus,
  canEdit,
  onVissza,
  onMentve,
}: {
  /** A megnyitott mentett ajánlat/sablon - null: új, üres ajánlat. */
  mentett: Arajanlat | null;
  katalogus: ArajanlatTetel[];
  canEdit: boolean;
  onVissza: () => void;
  onMentve: () => void;
}) {
  const [brand, setBrand] = useState(mentett?.brand ?? "hype");
  const [adat, setAdat] = useState<ArajanlatAdat>(() =>
    mentett ? ajanlatAdatBetoltes(mentett.adat, mentett.brand) : uresAjanlat("hype"),
  );
  // Sablonból nyitott ajánlat ÚJ rekordként mentődik (a sablon marad) - a
  // saját azonosítóját csak a nem-sablon szerkesztése őrzi.
  const [mentettId, setMentettId] = useState<number | null>(
    mentett && !mentett.sablon ? mentett.id : null,
  );
  const [nev, setNev] = useState(mentett && !mentett.sablon ? mentett.nev : "");
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [katalogusNyitva, setKatalogusNyitva] = useState(false);

  const osszeg = useMemo(() => osszesites(adat), [adat]);
  const brandBeallitas = BRAND_BEALLITAS[brand] ?? BRAND_BEALLITAS.hype;
  const tobbBlokk = adat.blokkok.length > 1;

  function mezot<K extends keyof ArajanlatAdat>(kulcs: K, ertek: ArajanlatAdat[K]) {
    setAdat((a) => ({ ...a, [kulcs]: ertek }));
  }

  function blokkot(blokkId: string, valtozas: (bl: ArajanlatBlokk) => ArajanlatBlokk) {
    setAdat((a) => ({ ...a, blokkok: a.blokkok.map((bl) => (bl.id === blokkId ? valtozas(bl) : bl)) }));
  }

  function szekciot(blokkId: string, szekcioId: string, valtozas: (sz: ArajanlatSzekcio) => ArajanlatSzekcio) {
    blokkot(blokkId, (bl) => ({
      ...bl,
      szekciok: bl.szekciok.map((sz) => (sz.id === szekcioId ? valtozas(sz) : sz)),
    }));
  }

  function tetelt(
    blokkId: string,
    szekcioId: string,
    tetelId: string,
    valtozas: (t: ArajanlatTetelSor) => ArajanlatTetelSor,
  ) {
    szekciot(blokkId, szekcioId, (sz) => ({
      ...sz,
      tetelek: sz.tetelek.map((t) => (t.id === tetelId ? valtozas(t) : t)),
    }));
  }

  function brandValtas(uj: string) {
    const regi = BRAND_BEALLITAS[brand] ?? BRAND_BEALLITAS.hype;
    const kovetkezo = BRAND_BEALLITAS[uj] ?? BRAND_BEALLITAS.hype;
    setBrand(uj);
    // A cégnevet csak akkor cseréljük, ha még az előző brand alapértéke állt
    // benne - egy kézzel átírt cégnevet nem bántunk.
    setAdat((a) => ({
      ...a,
      cegnev: a.cegnev === regi.cegnev || !a.cegnev ? kovetkezo.cegnev : a.cegnev,
      labCeg: a.labCeg === regi.cegnev || !a.labCeg ? kovetkezo.cegnev : a.labCeg,
    }));
  }

  /** Katalógus-tétel az UTOLSÓ blokkba, a vele azonos nevű szekcióba (ha
   * nincs ilyen, a szekció is létrejön) - a felhasználó kérése: az alap
   * tételek egy kattintással kerüljenek be. */
  function katalogusbol(tetel: ArajanlatTetel) {
    setAdat((a) => {
      const blokkok = a.blokkok.length > 0 ? [...a.blokkok] : [uresBlokk()];
      const utolso = { ...blokkok[blokkok.length - 1] };
      const szekcioNev = (tetel.szekcio ?? "").trim();
      let szekciok = [...utolso.szekciok];
      let cel = szekciok.find((sz) => sz.nev.trim().toLowerCase() === szekcioNev.toLowerCase());
      if (!cel) {
        if (szekcioNev) {
          cel = { id: ujId(), nev: szekcioNev, tetelek: [] };
          szekciok = [...szekciok, cel];
        } else {
          cel = szekciok[szekciok.length - 1] ?? { id: ujId(), nev: "", tetelek: [] };
          if (!utolso.szekciok.includes(cel)) szekciok = [...szekciok, cel];
        }
      }
      const ujTetel: ArajanlatTetelSor = {
        id: ujId(),
        nev: tetel.nev,
        megjegyzes: tetel.megjegyzes ?? "",
        alkalom: "1",
        mennyiseg: "1",
        egysegar: tetel.egysegar !== null ? osszegSzoveg(tetel.egysegar) : "0",
      };
      // Üres kezdő sort (se név, se ár) a katalógus-tétel lecserél, hogy ne
      // maradjon ott egy kitöltetlen sor a beszúrt fölött.
      const megtartott = cel.tetelek.filter((t) => t.nev.trim() || szamErtek(t.egysegar) !== 0);
      const ujSzekciok = szekciok.map((sz) =>
        sz.id === cel!.id ? { ...sz, tetelek: [...megtartott, ujTetel] } : sz,
      );
      blokkok[blokkok.length - 1] = { ...utolso, szekciok: ujSzekciok };
      return { ...a, blokkok };
    });
  }

  async function mentes(sablonkent: boolean) {
    let mentesiNev = nev.trim();
    if (sablonkent || !mentesiNev) {
      const javaslat = sablonkent
        ? mentesiNev || adat.blokkok[0]?.cim || "Ajánlat-sablon"
        : [adat.szam, adat.cimzettNev].filter(Boolean).join(" – ") || "Árajánlat";
      const beirt = window.prompt(
        sablonkent ? "A sablon neve (pl. 1 kamerás esemény videó):" : "Az ajánlat neve a listában:",
        javaslat,
      );
      if (beirt === null) return;
      mentesiNev = beirt.trim() || javaslat;
      if (!sablonkent) setNev(mentesiNev);
    }
    setBusy(true);
    setUzenet(null);
    try {
      const torzs = {
        nev: mentesiNev,
        sablon: sablonkent,
        brand,
        ugyfel: adat.cimzettNev.trim() || null,
        vegosszeg: Math.round(osszeg.fizetendo * 100) / 100,
        adat,
      };
      const frissitheto = !sablonkent && mentettId !== null;
      const res = await authFetch(
        frissitheto ? `/api/v1/arajanlatok/${mentettId}` : "/api/v1/arajanlatok",
        { method: frissitheto ? "PATCH" : "POST", body: JSON.stringify(torzs) },
      );
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        setUzenet(`Sikertelen mentés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      if (!sablonkent && !frissitheto) {
        const letrejott = (await res.json().catch(() => null)) as { id?: number } | null;
        if (letrejott?.id) setMentettId(letrejott.id);
      }
      setUzenet(sablonkent ? "Sablonként elmentve." : "Elmentve.");
      onMentve();
    } catch (err) {
      setUzenet(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  /** PDF: a böngésző nyomtatása, a fájlnév az ajánlat számából/címzettből. */
  function pdf() {
    const nevjavaslat = ["Arajanlat", adat.szam, adat.cimzettNev]
      .filter(Boolean)
      .join("_")
      .replace(/[\\/:*?"<>|]/g, "-")
      .replace(/\s+/g, "_");
    const regi = document.title;
    document.title = nevjavaslat || "Arajanlat";
    const vissza = () => {
      document.title = regi;
      window.removeEventListener("afterprint", vissza);
    };
    window.addEventListener("afterprint", vissza);
    window.print();
  }

  const katalogusSzekciok = useMemo(() => {
    const csoportok = new Map<string, ArajanlatTetel[]>();
    for (const t of [...katalogus].sort((a, b) => a.sorrend - b.sorrend || a.nev.localeCompare(b.nev, "hu"))) {
      const kulcs = (t.szekcio ?? "").trim() || "Egyéb";
      csoportok.set(kulcs, [...(csoportok.get(kulcs) ?? []), t]);
    }
    return [...csoportok.entries()];
  }, [katalogus]);

  return (
    <div className="aj-szerkeszto">
      {/* eszköztár - nyomtatásban nem látszik */}
      <div className="mb-4 flex flex-wrap items-center gap-2 print:hidden">
        <button type="button" onClick={onVissza} className="btn text-[13px]">
          ← Vissza a listához
        </button>
        <span className="mx-1 h-5 w-px bg-border" />
        {/* HYPE / ContentBee kapcsoló (a felhasználó kérése) */}
        {Object.entries(BRAND_BEALLITAS).map(([kulcs, b]) => (
          <button
            key={kulcs}
            type="button"
            onClick={() => brandValtas(kulcs)}
            className={`rounded-[var(--radius)] border px-3 py-1.5 text-[13px] ${
              brand === kulcs
                ? "border-text-accent/40 bg-bg-accent text-text-accent"
                : "border-border text-text-secondary hover:bg-surface-3"
            }`}
          >
            {b.nev}
          </button>
        ))}
        <span className="mx-1 h-5 w-px bg-border" />
        <button
          type="button"
          onClick={() => setAdat((a) => ({ ...a, blokkok: [...a.blokkok, uresBlokk()] }))}
          className="btn text-[13px]"
        >
          + Új esemény / blokk
        </button>
        <button
          type="button"
          onClick={() => mezot("afaLatszik", !adat.afaLatszik)}
          className="btn text-[13px]"
        >
          ÁFA sor {adat.afaLatszik ? "ki" : "be"}
        </button>
        <button
          type="button"
          onClick={() => setKatalogusNyitva((n) => !n)}
          className={`rounded-[var(--radius)] border px-3 py-1.5 text-[13px] ${
            katalogusNyitva
              ? "border-text-accent/40 bg-bg-accent text-text-accent"
              : "border-border text-text-secondary hover:bg-surface-3"
          }`}
        >
          Alap tételek
        </button>
        <span className="flex-1" />
        {uzenet && <span className="text-[12.5px] text-text-muted">{uzenet}</span>}
        {canEdit && (
          <>
            <button type="button" disabled={busy} onClick={() => mentes(true)} className="btn text-[13px]">
              Mentés sablonként
            </button>
            <button type="button" disabled={busy} onClick={() => mentes(false)} className="btn btn-primary text-[13px]">
              {mentettId !== null ? "Mentés" : "Mentés ajánlatként"}
            </button>
          </>
        )}
        <button type="button" onClick={pdf} className="btn text-[13px]">
          PDF / nyomtatás
        </button>
      </div>

      {/* alap tétel-katalógus panel */}
      {katalogusNyitva && (
        <div className="mb-4 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4 print:hidden">
          <p className="mb-2 text-[12.5px] text-text-muted">
            Kattints egy tételre – az utolsó blokkba kerül, a saját szekciójába. A katalógus a lista oldalon
            szerkeszthető.
          </p>
          {katalogusSzekciok.length === 0 && (
            <p className="text-[13px] text-text-secondary">Még nincs alap tétel felvéve.</p>
          )}
          <div className="flex flex-wrap gap-4">
            {katalogusSzekciok.map(([szekcio, tetelek]) => (
              <div key={szekcio} className="min-w-[220px]">
                <p className="mb-1 text-[11px] uppercase tracking-wide text-text-muted">{szekcio}</p>
                <div className="flex flex-col gap-1">
                  {tetelek.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => katalogusbol(t)}
                      className="rounded-[var(--radius)] border border-border bg-surface-1 px-2.5 py-1.5 text-left text-[13px] text-text-primary hover:border-text-accent/50"
                    >
                      <span className="font-medium">{t.nev}</span>
                      {t.egysegar !== null && (
                        <span className="text-text-muted"> · {osszegSzoveg(t.egysegar)} Ft</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---------- maga a lap ---------- */}
      <div className="aj-wrap">
        <div className="aj-sheet aj-print-cel">
          <div className="aj-head">
            <div>
              <div className="aj-logo">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={brandBeallitas.logo} alt={`${brandBeallitas.nev} logó`} />
              </div>
              <input
                className="aj-be aj-conev"
                value={adat.cegnev}
                onChange={(e) => mezot("cegnev", e.target.value)}
                placeholder="Cégnév"
              />
              <textarea
                className="aj-be aj-colines"
                rows={3}
                value={adat.cegadatok}
                onChange={(e) => mezot("cegadatok", e.target.value)}
                placeholder={"Cím\nAdószám\nE-mail · Telefon"}
              />
            </div>
            <div className="aj-doc">
              <h1>Árajánlat</h1>
              <div className="aj-meta">
                <span>Ajánlat sz.</span>
                <input className="aj-be" value={adat.szam} onChange={(e) => mezot("szam", e.target.value)} placeholder="2026/001" />
                <span>Kelt</span>
                <input className="aj-be" value={adat.kelt} onChange={(e) => mezot("kelt", e.target.value)} placeholder="2026.01.01." />
                <span>Érvényes</span>
                <input className="aj-be" value={adat.ervenyes} onChange={(e) => mezot("ervenyes", e.target.value)} placeholder="30 napig" />
                <span>Pénznem</span>
                <input className="aj-be" value={adat.penznem} onChange={(e) => mezot("penznem", e.target.value)} placeholder="Ft" />
              </div>
            </div>
          </div>

          <div className="aj-rule" />

          <div className="aj-parties">
            <div>
              <div className="aj-label">Ajánlat címzettje</div>
              <input
                className="aj-be aj-party-nev"
                value={adat.cimzettNev}
                onChange={(e) => mezot("cimzettNev", e.target.value)}
                placeholder="Ügyfél neve"
              />
              <textarea
                className="aj-be aj-party-sorok"
                rows={3}
                value={adat.cimzettAdatok}
                onChange={(e) => mezot("cimzettAdatok", e.target.value)}
                placeholder={"Kapcsolattartó\nCím\nE-mail"}
              />
            </div>
            <div>
              <div className="aj-label">Kapcsolattartó nálunk</div>
              <input
                className="aj-be aj-party-nev"
                value={adat.kapcsolatNev}
                onChange={(e) => mezot("kapcsolatNev", e.target.value)}
                placeholder="Neved"
              />
              <textarea
                className="aj-be aj-party-sorok"
                rows={3}
                value={adat.kapcsolatAdatok}
                onChange={(e) => mezot("kapcsolatAdatok", e.target.value)}
                placeholder={"Pozíció\nE-mail · Telefon"}
              />
            </div>
          </div>

          <div className="aj-blocks">
            {adat.blokkok.map((bl, bi) => (
              <div key={bl.id} className="aj-block">
                {adat.blokkok.length > 1 && (
                  <button
                    type="button"
                    className="aj-block-del"
                    title="Blokk törlése"
                    onClick={() => {
                      if (window.confirm("Biztosan törlöd ezt a blokkot a tételeivel együtt?")) {
                        setAdat((a) => ({ ...a, blokkok: a.blokkok.filter((x) => x.id !== bl.id) }));
                      }
                    }}
                  >
                    ×
                  </button>
                )}
                <div className="aj-block-head">
                  <div className="aj-block-cimek">
                    {tobbBlokk && <div className="aj-idx">{bi + 1}. esemény</div>}
                    <input
                      className="aj-be aj-block-title"
                      value={bl.cim}
                      onChange={(e) => blokkot(bl.id, (x) => ({ ...x, cim: e.target.value }))}
                      placeholder="Esemény / projekt megnevezése"
                    />
                    <input
                      className="aj-be aj-block-desc"
                      value={bl.leiras}
                      onChange={(e) => blokkot(bl.id, (x) => ({ ...x, leiras: e.target.value }))}
                      placeholder="Rövid leírás: helyszín, forgatási napok, leadás"
                    />
                  </div>
                  {tobbBlokk && (
                    <div className="aj-block-right">
                      <div className="aj-sum-label">Blokk összesen</div>
                      <div className="aj-b-sum">
                        {osszegSzoveg(blokkOsszeg(bl))} {adat.penznem}
                      </div>
                    </div>
                  )}
                </div>

                <div className="aj-tablescroll">
                  <table>
                    <colgroup>
                      <col />
                      <col className="aj-c-occ" />
                      <col className="aj-c-qty" />
                      <col className="aj-c-price" />
                      <col className="aj-c-sum" />
                      <col className="aj-c-act" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th>Tétel</th>
                        <th>Alkalom</th>
                        <th>Mennyiség</th>
                        <th>Egységár</th>
                        <th>Teljes ár</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {bl.szekciok.map((sz) => (
                        <SzekcioSorok
                          key={sz.id}
                          blokk={bl}
                          szekcio={sz}
                          penznem={adat.penznem}
                          onSzekcio={(v) => szekciot(bl.id, sz.id, v)}
                          onTetel={(tetelId, v) => tetelt(bl.id, sz.id, tetelId, v)}
                          onSzekcioTorles={() =>
                            blokkot(bl.id, (x) => ({ ...x, szekciok: x.szekciok.filter((y) => y.id !== sz.id) }))
                          }
                        />
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="aj-addrow">
                  <button
                    type="button"
                    onClick={() =>
                      blokkot(bl.id, (x) => {
                        const szekciok = x.szekciok.length > 0 ? [...x.szekciok] : [uresSzekcio()];
                        const utolso = szekciok[szekciok.length - 1];
                        szekciok[szekciok.length - 1] = { ...utolso, tetelek: [...utolso.tetelek, uresTetel()] };
                        return { ...x, szekciok };
                      })
                    }
                  >
                    + Tétel
                  </button>
                  <button
                    type="button"
                    onClick={() => blokkot(bl.id, (x) => ({ ...x, szekciok: [...x.szekciok, uresSzekcio()] }))}
                  >
                    + Szekció
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="aj-sum-wrap">
            <div className="aj-sum">
              <div className="aj-row">
                <span className="aj-k">Részösszeg</span>
                <span className="aj-v">
                  {osszegSzoveg(osszeg.reszosszeg)} {adat.penznem}
                </span>
              </div>
              <div className={`aj-row${osszeg.kedvezmeny ? "" : " aj-zero"}`}>
                <span className="aj-k">
                  Kedvezmény{" "}
                  <input
                    className="aj-pct"
                    value={adat.kedvezmeny}
                    onChange={(e) => mezot("kedvezmeny", e.target.value)}
                  />
                  %
                </span>
                <span className="aj-v">
                  {osszeg.kedvezmeny ? "−" : ""}
                  {osszegSzoveg(osszeg.kedvezmeny)} {adat.penznem}
                </span>
              </div>
              <div className="aj-divider" />
              <div className="aj-row">
                <span className="aj-k">Nettó összesen</span>
                <span className="aj-v">
                  {osszegSzoveg(osszeg.netto)} {adat.penznem}
                </span>
              </div>
              {adat.afaLatszik && (
                <div className="aj-row">
                  <span className="aj-k">
                    ÁFA <input className="aj-pct" value={adat.afa} onChange={(e) => mezot("afa", e.target.value)} />%
                  </span>
                  <span className="aj-v">
                    {osszegSzoveg(osszeg.afa)} {adat.penznem}
                  </span>
                </div>
              )}
              <div className="aj-grand">
                <span className="aj-k">Fizetendő</span>
                <span className="aj-v">
                  {osszegSzoveg(osszeg.fizetendo)} {adat.penznem}
                </span>
              </div>
              <p className="aj-vat-note">
                {adat.afaLatszik ? "A feltüntetett végösszeg az ÁFA-t tartalmazza." : "Az árak az ÁFA-t nem tartalmazzák."}
              </p>
            </div>
          </div>

          <div className="aj-notes">
            <div>
              <div className="aj-label">Az ajánlat tartalmazza</div>
              <SorLista ertek={adat.tartalmazza} onChange={(v) => mezot("tartalmazza", v)} />
            </div>
            <div>
              <div className="aj-label">Feltételek</div>
              <SorLista ertek={adat.feltetelek} onChange={(v) => mezot("feltetelek", v)} />
            </div>
          </div>

          <div className="aj-sign">
            <input className="aj-be aj-sign-line" value={adat.alairo} onChange={(e) => mezot("alairo", e.target.value)} />
            <input
              className="aj-be aj-sign-line"
              value={adat.megrendeloSor}
              onChange={(e) => mezot("megrendeloSor", e.target.value)}
            />
          </div>

          <div className="aj-foot">
            <input className="aj-be" value={adat.labCeg} onChange={(e) => mezot("labCeg", e.target.value)} placeholder="Cégnév · weboldal" />
            <input
              className="aj-be aj-foot-jobb"
              value={adat.labBank}
              onChange={(e) => mezot("labBank", e.target.value)}
              placeholder="Bankszámlaszám"
            />
          </div>
        </div>
      </div>

      <ArajanlatLapStilus />
    </div>
  );
}

/** Egy szekció fejléc-sora + a tételei - a tábla törzsében. */
function SzekcioSorok({
  blokk,
  szekcio,
  penznem,
  onSzekcio,
  onTetel,
  onSzekcioTorles,
}: {
  blokk: ArajanlatBlokk;
  szekcio: ArajanlatSzekcio;
  penznem: string;
  onSzekcio: (v: (sz: ArajanlatSzekcio) => ArajanlatSzekcio) => void;
  onTetel: (tetelId: string, v: (t: ArajanlatTetelSor) => ArajanlatTetelSor) => void;
  onSzekcioTorles: () => void;
}) {
  return (
    <>
      <tr className="aj-section">
        <td colSpan={4}>
          <input
            className="aj-be aj-sec-name"
            value={szekcio.nev}
            onChange={(e) => onSzekcio((sz) => ({ ...sz, nev: e.target.value }))}
            placeholder="Szekció neve"
          />
        </td>
        <td>
          <span className="aj-sec-sum">
            {osszegSzoveg(szekcioOsszeg(szekcio))} {penznem}
          </span>
        </td>
        <td>
          {blokk.szekciok.length > 1 && (
            <button type="button" className="aj-del" title="Szekció törlése" onClick={onSzekcioTorles}>
              ×
            </button>
          )}
        </td>
      </tr>
      {szekcio.tetelek.map((t) => (
        <tr key={t.id} className="aj-item">
          <td>
            <input
              className="aj-be aj-it-name"
              value={t.nev}
              onChange={(e) => onTetel(t.id, (x) => ({ ...x, nev: e.target.value }))}
              placeholder="Tétel neve"
            />
            <input
              className="aj-be aj-it-note"
              value={t.megjegyzes}
              onChange={(e) => onTetel(t.id, (x) => ({ ...x, megjegyzes: e.target.value }))}
              placeholder="Megjegyzés (opcionális)"
            />
          </td>
          <td>
            <input
              className="aj-num"
              inputMode="decimal"
              value={t.alkalom}
              onChange={(e) => onTetel(t.id, (x) => ({ ...x, alkalom: e.target.value }))}
            />
          </td>
          <td>
            <input
              className="aj-num"
              inputMode="decimal"
              value={t.mennyiseg}
              onChange={(e) => onTetel(t.id, (x) => ({ ...x, mennyiseg: e.target.value }))}
            />
          </td>
          <td>
            <input
              className="aj-num"
              inputMode="decimal"
              value={t.egysegar}
              onChange={(e) => onTetel(t.id, (x) => ({ ...x, egysegar: e.target.value }))}
              onBlur={(e) => {
                if (e.target.value.trim() === "") return;
                onTetel(t.id, (x) => ({ ...x, egysegar: osszegSzoveg(szamErtek(x.egysegar)) }));
              }}
            />
          </td>
          <td>
            <span className="aj-total">{osszegSzoveg(tetelOsszeg(t))}</span>
          </td>
          <td>
            <button
              type="button"
              className="aj-del"
              title="Sor törlése"
              onClick={() => onSzekcio((sz) => ({ ...sz, tetelek: sz.tetelek.filter((x) => x.id !== t.id) }))}
            >
              ×
            </button>
          </td>
        </tr>
      ))}
    </>
  );
}

/** Soronként-egy-pont szöveg: szerkesztésben textarea, nyomtatásban lista. */
function SorLista({ ertek, onChange }: { ertek: string; onChange: (v: string) => void }) {
  const sorok = ertek
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  return (
    <div className="aj-body">
      <textarea
        className="aj-be aj-lista-szerk"
        rows={Math.max(4, sorok.length + 1)}
        value={ertek}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Soronként egy pont"
      />
      <ul className="aj-lista-nyomtat">
        {sorok.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
    </div>
  );
}

/** A lap saját stíluslapja - a feltöltött sablon kinézete, "aj-" előtaggal
 * hatókörözve. A lap MINDIG világos (papír), és a print-blokk gondoskodik
 * róla, hogy nyomtatáskor csak a lap kerüljön papírra. */
function ArajanlatLapStilus() {
  return (
    <style>{`
.aj-szerkeszto{
  --aj-sheet:#ffffff; --aj-ink:#0C1114; --aj-ink2:#44525A; --aj-ink3:#7A8990;
  --aj-line:#D5DEE1; --aj-line-soft:#E9EEF0;
  --aj-accent:#0E7C86; --aj-accent-ink:#0A5A62; --aj-band:#F2F7F7;
  --aj-danger:#B4442C;
  --aj-num:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Menlo,monospace;
}
.aj-wrap{display:flex; justify-content:center}
.aj-sheet{
  width:100%; max-width:820px; background:var(--aj-sheet); color:var(--aj-ink);
  box-shadow:0 1px 2px rgba(12,17,20,.08), 0 18px 45px -22px rgba(12,17,20,.35);
  padding:52px 56px 44px; font-size:15px; line-height:1.5;
}
.aj-be{
  border:0; background:transparent; color:inherit; font:inherit; width:100%;
  padding:1px 2px; border-radius:2px; resize:vertical;
}
.aj-be:hover{background:var(--aj-line-soft)}
.aj-be:focus-visible{outline:2px solid var(--aj-accent); outline-offset:1px}
.aj-be::placeholder{color:var(--aj-ink3)}

.aj-head{display:flex; gap:32px; align-items:flex-start; justify-content:space-between}
.aj-logo img{max-width:150px; max-height:96px; display:block}
.aj-conev{font-weight:700; font-size:19px; letter-spacing:-.01em; margin-top:14px}
.aj-colines{font-size:13.5px; color:var(--aj-ink2); line-height:1.55; margin-top:3px}
.aj-doc{text-align:right; min-width:250px}
.aj-doc h1{
  font-weight:600; font-size:13px; letter-spacing:.28em; text-transform:uppercase;
  color:var(--aj-accent); margin:0 0 12px;
}
.aj-meta{display:grid; grid-template-columns:auto 130px; gap:5px 16px; justify-content:end; align-items:baseline}
.aj-meta span{font-family:var(--aj-num); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--aj-ink3); text-align:right}
.aj-meta .aj-be{font-family:var(--aj-num); font-size:13px; text-align:right}

.aj-rule{height:1px; background:var(--aj-ink); opacity:.85; margin:26px 0 0}

.aj-parties{display:grid; grid-template-columns:1fr 1fr; gap:36px; margin-top:26px}
.aj-label{font-family:var(--aj-num); font-size:10px; letter-spacing:.16em; text-transform:uppercase; color:var(--aj-ink3); margin-bottom:6px}
.aj-party-nev{font-weight:600; font-size:15.5px}
.aj-party-sorok{font-size:13.5px; color:var(--aj-ink2); line-height:1.55}

.aj-blocks{display:flex; flex-direction:column; gap:34px; margin-top:34px}
.aj-block{position:relative}
.aj-block-head{
  display:flex; align-items:flex-start; justify-content:space-between; gap:24px;
  background:var(--aj-band); padding:15px 20px; border-left:3px solid var(--aj-accent);
}
.aj-block-cimek{flex:1; min-width:0}
.aj-idx{font-family:var(--aj-num); font-size:10px; letter-spacing:.18em; text-transform:uppercase; color:var(--aj-accent-ink); margin-bottom:5px}
.aj-block-title{font-weight:600; font-size:19px; letter-spacing:-.01em}
.aj-block-desc{font-size:13.5px; color:var(--aj-ink2); margin-top:3px}
.aj-block-right{text-align:right; white-space:nowrap}
.aj-sum-label{font-family:var(--aj-num); font-size:9.5px; letter-spacing:.16em; text-transform:uppercase; color:var(--aj-ink3)}
.aj-b-sum{font-family:var(--aj-num); font-size:15px; font-variant-numeric:tabular-nums; margin-top:2px}
.aj-block-del{
  position:absolute; top:-11px; right:-11px; width:24px; height:24px; padding:0; line-height:1;
  border-radius:50%; background:var(--aj-sheet); border:1px solid var(--aj-line); color:var(--aj-ink3);
  font-size:14px; opacity:0; transition:opacity .12s ease; cursor:pointer;
}
.aj-block:hover .aj-block-del{opacity:1}
.aj-block-del:hover{color:var(--aj-danger); border-color:var(--aj-danger)}

.aj-sheet table{width:100%; border-collapse:collapse; margin-top:14px}
.aj-sheet thead th{
  font-family:var(--aj-num); font-weight:500; font-size:10px;
  letter-spacing:.13em; text-transform:uppercase; color:var(--aj-ink3);
  text-align:right; padding:0 8px 8px; border-bottom:1px solid var(--aj-ink); white-space:nowrap;
}
.aj-sheet thead th:first-child{text-align:left; padding-left:0}
.aj-sheet tbody td{padding:11px 8px; border-bottom:1px solid var(--aj-line-soft); vertical-align:top; text-align:right}
.aj-sheet tbody td:first-child{text-align:left; padding-left:0}
.aj-it-name{font-weight:600; font-size:14.5px; line-height:1.35}
.aj-it-note{font-size:12.5px; color:var(--aj-ink2); line-height:1.4; margin-top:2px}
.aj-num{
  font-family:var(--aj-num); font-size:13px; font-variant-numeric:tabular-nums;
  width:100%; text-align:right; border:0; background:transparent; color:var(--aj-ink);
  padding:2px 4px; border-radius:2px;
}
.aj-num:hover{background:var(--aj-line-soft)}
.aj-num:focus-visible{outline:2px solid var(--aj-accent); outline-offset:1px}
.aj-total{font-family:var(--aj-num); font-size:13px; font-variant-numeric:tabular-nums; white-space:nowrap}
.aj-c-occ{width:64px}.aj-c-qty{width:74px}.aj-c-price{width:112px}.aj-c-sum{width:118px}.aj-c-act{width:30px}

tr.aj-section td{border-top:1px solid var(--aj-line); border-bottom:1px solid var(--aj-line-soft); padding-top:12px; padding-bottom:8px}
.aj-sec-name{font-weight:600; font-size:12px; letter-spacing:.16em; text-transform:uppercase; color:var(--aj-accent-ink)}
.aj-sec-sum{font-family:var(--aj-num); font-size:12px; color:var(--aj-accent-ink); font-variant-numeric:tabular-nums}

.aj-del{
  border:0; background:transparent; color:var(--aj-ink3); cursor:pointer;
  padding:2px 4px; font-size:16px; line-height:1; opacity:0; transition:opacity .12s ease;
}
tr:hover .aj-del{opacity:1}
.aj-del:hover{color:var(--aj-danger)}
.aj-addrow{display:flex; gap:8px; margin-top:12px}
.aj-addrow button{
  font-size:12.5px; padding:5px 10px; color:var(--aj-ink2); cursor:pointer;
  background:transparent; border:1px solid var(--aj-line); border-radius:3px;
}
.aj-addrow button:hover{background:var(--aj-line-soft)}

.aj-sum-wrap{display:flex; justify-content:flex-end; margin-top:34px}
.aj-sum{width:340px; max-width:100%}
.aj-row{display:flex; justify-content:space-between; align-items:center; gap:16px; padding:7px 0; font-size:14px}
.aj-row .aj-k{color:var(--aj-ink2)}
.aj-row .aj-v{font-family:var(--aj-num); font-size:13.5px; font-variant-numeric:tabular-nums; white-space:nowrap}
.aj-divider{height:1px; background:var(--aj-line); margin:4px 0}
.aj-grand{
  display:flex; justify-content:space-between; align-items:baseline; gap:16px;
  margin-top:10px; padding:15px 18px; background:var(--aj-band); border-left:3px solid var(--aj-accent);
}
.aj-grand .aj-k{font-family:var(--aj-num); font-size:10.5px; letter-spacing:.16em; text-transform:uppercase; color:var(--aj-ink3)}
.aj-grand .aj-v{font-weight:700; font-size:22px; font-variant-numeric:tabular-nums; letter-spacing:-.01em}
.aj-pct{
  width:52px; font-family:var(--aj-num); font-size:13px; text-align:right;
  border:1px solid var(--aj-line); border-radius:2px; background:transparent; color:var(--aj-ink); padding:1px 4px;
}
.aj-vat-note{font-size:12px; color:var(--aj-ink3); text-align:right; margin-top:8px; font-style:italic}

.aj-notes{margin-top:38px; display:grid; grid-template-columns:1fr 1fr; gap:36px}
.aj-body{font-size:13px; color:var(--aj-ink2); line-height:1.6}
.aj-lista-szerk{min-height:90px}
.aj-lista-nyomtat{display:none; margin:0; padding-left:16px}
.aj-lista-nyomtat li{margin-bottom:3px}
.aj-sign{margin-top:44px; display:grid; grid-template-columns:1fr 1fr; gap:36px; align-items:end}
.aj-sign-line{border-top:1px solid var(--aj-line); border-radius:0; padding-top:7px; font-size:12px; color:var(--aj-ink3); font-family:var(--aj-num); letter-spacing:.06em}
.aj-foot{margin-top:34px; padding-top:12px; border-top:1px solid var(--aj-line-soft); display:flex; justify-content:space-between; gap:20px; font-size:11.5px; color:var(--aj-ink3)}
.aj-foot .aj-be{font-size:11.5px; color:var(--aj-ink3)}
.aj-foot-jobb{text-align:right}

@media (max-width:720px){
  .aj-sheet{padding:32px 22px}
  .aj-head{flex-direction:column; gap:20px}
  .aj-doc{text-align:left; min-width:0}
  .aj-meta{justify-content:start}
  .aj-meta span, .aj-meta .aj-be{text-align:left}
  .aj-parties,.aj-notes,.aj-sign{grid-template-columns:1fr; gap:20px}
  .aj-sum{width:100%}
  .aj-block-head{flex-direction:column; gap:10px}
  .aj-block-right{text-align:left}
  .aj-tablescroll{overflow-x:auto}
  .aj-sheet table{min-width:600px}
}

@page{size:A4; margin:0}
@media print{
  /* Csak a lap megy papírra: minden más láthatatlan, a lap a bal felső
     sarokból indul (visibility-trükk - a display:none az elrendezést is
     elvinné a lap alól). */
  body *{visibility:hidden !important}
  .aj-print-cel, .aj-print-cel *{visibility:visible !important}
  .aj-print-cel{position:absolute !important; left:0; top:0; width:100%; max-width:none; box-shadow:none; padding:15mm 16mm 13mm}
  .aj-print-cel{font-size:10.6pt}
  .aj-del,.aj-block-del,.aj-addrow{display:none !important}
  .aj-be::placeholder{color:transparent}
  .aj-lista-szerk{display:none}
  .aj-lista-nyomtat{display:block}
  .aj-row.aj-zero{display:none}
  .aj-be:hover,.aj-num:hover{background:transparent}
  .aj-pct{border-color:transparent; padding:0; width:auto}
  .aj-grand{padding:12px 14px}
  .aj-grand .aj-v{font-size:17pt}
  .aj-block-head{break-inside:avoid; break-after:avoid}
  tr,.aj-sum-wrap,.aj-notes,.aj-sign{break-inside:avoid}
  thead{display:table-header-group}
  *{-webkit-print-color-adjust:exact !important; print-color-adjust:exact !important}
}
`}</style>
  );
}
