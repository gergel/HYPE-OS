"use client";

import { Fragment, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import type { DocumentAttachment } from "@/lib/api";

/** A szövegben talált linkek kattinthatóvá tétele.
 *
 * Miért nem elég a nyers szöveg? Mert ide a gyakorlatban linkek kerülnek
 * (Drive-mappa, helyszín a térképen, forgatókönyv) - kijelölni és átmásolni
 * őket minden alkalommal fölösleges munka.
 *
 * Szándékosan NEM kockázatos HTML-t renderelünk: a szöveget darabokra vágjuk,
 * és a link-darabokból csinálunk <a>-t. Így a beírt szöveg soha nem tud
 * jelölésként viselkedni, a sortörések pedig megmaradnak (whitespace-pre-wrap).
 *
 * A záró írásjeleket (zárójel, pont, vessző) leválasztjuk a linkről: a "nézd
 * meg itt: https://…/x." mondat végi pontja nem a cím része. */
const LINK_MINTA = /((?:https?:\/\/|www\.)[^\s<>]+)/gi;

export function linkesitve(szoveg: string): React.ReactNode[] {
  return szoveg.split(LINK_MINTA).map((resz, i) => {
    if (i % 2 === 0) return <Fragment key={i}>{resz}</Fragment>;
    const zaro = resz.match(/[).,;:!?]+$/)?.[0] ?? "";
    const cim = zaro ? resz.slice(0, -zaro.length) : resz;
    const href = cim.startsWith("http") ? cim : `https://${cim}`;
    return (
      <Fragment key={i}>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="break-all text-text-accent hover:underline"
        >
          {cim}
        </a>
        {zaro}
      </Fragment>
    );
  });
}

/** A projekt GYÁRTÁS KOMMENT doboza: szabad szöveg (több sor, kattintható
 * linkekkel) és a hozzá tartozó fájlok.
 *
 * Ez a gyártásvezető jegyzettömbje a projekten: mi a helyzet, mit kell tudni,
 * hova kerültek az anyagok. Ezért nem egysoros mező: a sortörések megmaradnak,
 * a beillesztett linkek kattinthatók, a kapcsolódó fájlok (forgatókönyv,
 * helyszínrajz, brief) pedig ugyanitt élnek - `gyartas` kategóriával, hogy ne
 * keveredjenek a diszpó mellékleteivel. */
export function GyartasKomment({
  projectId,
  patchPath,
  ertek,
  attachments,
  canEdit,
  canDelete,
}: {
  projectId: number;
  patchPath: string;
  ertek: string | null;
  attachments: DocumentAttachment[];
  canEdit: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const [szerkeszt, setSzerkeszt] = useState(false);
  const [szoveg, setSzoveg] = useState(ertek ?? "");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function ment() {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(patchPath, {
        method: "PATCH",
        body: JSON.stringify({ gyartas_komment: szoveg.trim() || null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      setSzerkeszt(false);
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {szerkeszt ? (
        <>
          <textarea
            autoFocus
            rows={8}
            value={szoveg}
            onChange={(e) => setSzoveg(e.target.value)}
            placeholder={"Bármi, amit a gyártásról tudni kell.\nLinkeket is beilleszthetsz - mentés után kattinthatók lesznek."}
            className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] leading-relaxed text-text-primary outline-none focus:border-text-accent/40"
          />
          {hiba && <p className="text-[12px] text-text-danger">{hiba}</p>}
          <div className="flex gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={ment}
              className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Mentés…" : "Mentés"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setSzoveg(ertek ?? "");
                setHiba(null);
                setSzerkeszt(false);
              }}
              className="text-[13px] text-text-muted hover:text-text-primary"
            >
              Mégse
            </button>
          </div>
        </>
      ) : (
        <>
          {/* whitespace-pre-wrap: a bekezdések és a felsorolások úgy maradnak,
              ahogy beírták - egy egysoros mezőben ez elveszne. */}
          {ertek?.trim() ? (
            <p className="whitespace-pre-wrap break-words text-[13px] leading-relaxed text-text-primary">
              {linkesitve(ertek)}
            </p>
          ) : (
            <p className="text-[13px] text-text-muted">Még nincs gyártás komment.</p>
          )}
          {canEdit && (
            <button
              type="button"
              onClick={() => {
                setSzoveg(ertek ?? "");
                setSzerkeszt(true);
              }}
              className="w-fit text-[13px] text-text-accent hover:underline"
            >
              {ertek?.trim() ? "Szerkesztés" : "+ Komment írása"}
            </button>
          )}
        </>
      )}

      <div className="border-t border-border pt-3">
        <DokumentumFeltoltes
          entityType="project"
          entityId={projectId}
          attachments={attachments}
          kategoria="gyartas"
          canEdit={canEdit}
          canDelete={canDelete}
          emptyText="Nincs ide feltöltött fájl."
        />
      </div>
    </div>
  );
}
