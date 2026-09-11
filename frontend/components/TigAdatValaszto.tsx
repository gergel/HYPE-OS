"use client";

import { useEffect, useState } from "react";
import { KeresosSelect } from "@/components/KeresosSelect";
import { authFetch } from "@/lib/authFetch";

/** Egy ismert adat-készlet a TIG-űrlaphoz (lásd backend
 * performance_certificates.tig_adat_javaslatok). */
export type TigAdatJavaslat = {
  forras: string;
  ceg_neve: string | null;
  szekhely: string | null;
  adoszam: string | null;
  megbizas_targya: string | null;
  plusz_afa: boolean | null;
};

/** "Kitöltés mentett adatokból" választó a TIG-űrlapok tetején (a felhasználó
 * kérése: a mezőket listából lehessen kitölteni, ne kelljen gépelni). A
 * választék a fél adatlapja + a korábbi TIG-jei és szerződései - a
 * kiválasztott készlet a cégadat-mezőket tölti, az összeghez/dátumhoz nem
 * nyúl. Minden mező utána is szabadon átírható. */
export function TigAdatValaszto({
  szamlazoKulcs,
  disabled = false,
  onValaszt,
}: {
  szamlazoKulcs: string;
  disabled?: boolean;
  onValaszt: (javaslat: TigAdatJavaslat) => void;
}) {
  const [javaslatok, setJavaslatok] = useState<TigAdatJavaslat[] | null>(null);

  useEffect(() => {
    let aktiv = true;
    authFetch(`/api/v1/teljesitesi-igazolasok/adat-javaslatok/${szamlazoKulcs}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((adat: TigAdatJavaslat[]) => {
        if (aktiv) setJavaslatok(adat);
      })
      .catch(() => {
        if (aktiv) setJavaslatok([]);
      });
    return () => {
      aktiv = false;
    };
  }, [szamlazoKulcs]);

  if (!javaslatok || javaslatok.length === 0) return null;

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2">
      <span className="text-[12.5px] text-text-secondary">Kitöltés mentett adatokból:</span>
      <KeresosSelect
        value={null}
        options={javaslatok.map((j, i) => ({
          value: String(i),
          label: `${j.forras} – ${j.ceg_neve ?? "névtelen"}`,
          sublabel: [j.adoszam, j.szekhely].filter(Boolean).join(" · ") || undefined,
        }))}
        onChange={(ertek) => {
          const j = javaslatok[Number(ertek)];
          if (j) onValaszt(j);
        }}
        disabled={disabled}
        placeholder={`Válassz… (${javaslatok.length})`}
        className="min-w-[260px]"
      />
    </div>
  );
}
