"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import type { Arajanlat, ArajanlatListItem, ArajanlatTetel } from "@/lib/api";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { ArajanlatSzerkeszto } from "@/components/arajanlat/ArajanlatSzerkeszto";
import { BRAND_BEALLITAS, osszegSzoveg } from "@/components/arajanlat/arajanlatTipusok";

/** Az Árajánlatok oldal: mentett ajánlatok + visszahívható sablonok + az
 * alap tétel-katalógus - és maga a szerkesztő (lásd ArajanlatSzerkeszto).
 *
 * A szerkesztő nem külön útvonal, hanem a lista HELYÉN nyílik: így a
 * nyomtatás (PDF) alatt sincs körülötte más tartalom, és a "Vissza" nem
 * veszít oldal-állapotot. */
export function ArajanlatokContent({
  ajanlatok,
  tetelek,
  canEdit,
  canCreate,
  canDelete,
}: {
  ajanlatok: ArajanlatListItem[];
  tetelek: ArajanlatTetel[];
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const [szerkesztett, setSzerkesztett] = useState<Arajanlat | null | "uj">(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const sablonok = ajanlatok.filter((a) => a.sablon);
  const kiadottak = ajanlatok.filter((a) => !a.sablon);
  const irhat = canEdit || canCreate;

  async function megnyitas(id: number) {
    setBusyId(id);
    try {
      const res = await authFetch(`/api/v1/arajanlatok/${id}`);
      if (!res.ok) {
        alert(`Nem sikerült megnyitni (HTTP ${res.status}).`);
        return;
      }
      setSzerkesztett((await res.json()) as Arajanlat);
    } finally {
      setBusyId(null);
    }
  }

  async function torles(a: ArajanlatListItem) {
    if (!window.confirm(`Biztosan törlöd: ${a.nev}?`)) return;
    setBusyId(a.id);
    try {
      const res = await authFetch(`/api/v1/arajanlatok/${a.id}`, { method: "DELETE" });
      if (!res.ok) alert(`Nem sikerült törölni (HTTP ${res.status}).`);
      router.refresh();
    } finally {
      setBusyId(null);
    }
  }

  if (szerkesztett !== null) {
    return (
      <ArajanlatSzerkeszto
        mentett={szerkesztett === "uj" ? null : szerkesztett}
        katalogus={tetelek}
        canEdit={irhat}
        onVissza={() => {
          setSzerkesztett(null);
          router.refresh();
        }}
        onMentve={() => router.refresh()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card title="Árajánlatok">
        {irhat && (
          <button type="button" onClick={() => setSzerkesztett("uj")} className="btn btn-primary mb-4 text-[13px]">
            + Új árajánlat
          </button>
        )}
        {kiadottak.length === 0 ? (
          <p className="text-[13px] text-text-secondary">Még nincs mentett árajánlat.</p>
        ) : (
          <AjanlatTabla sorok={kiadottak} busyId={busyId} onMegnyitas={megnyitas} onTorles={canDelete ? torles : null} />
        )}
      </Card>

      <Card title="Sablonok">
        <p className="mb-3 text-[12.5px] text-text-muted">
          Egy kész ajánlat a szerkesztőben a „Mentés sablonként” gombbal kerül ide (pl. „1 kamerás esemény
          videó”) – megnyitva ÚJ ajánlat készül belőle, a sablon változatlan marad.
        </p>
        {sablonok.length === 0 ? (
          <p className="text-[13px] text-text-secondary">Még nincs sablon.</p>
        ) : (
          <AjanlatTabla sorok={sablonok} busyId={busyId} onMegnyitas={megnyitas} onTorles={canDelete ? torles : null} />
        )}
      </Card>

      <TetelKatalogus tetelek={tetelek} canEdit={irhat} canDelete={canDelete} />
    </div>
  );
}

function AjanlatTabla({
  sorok,
  busyId,
  onMegnyitas,
  onTorles,
}: {
  sorok: ArajanlatListItem[];
  busyId: number | null;
  onMegnyitas: (id: number) => void;
  onTorles: ((a: ArajanlatListItem) => void) | null;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="py-1.5 pr-6 font-medium text-text-secondary">Név</th>
            <th className="py-1.5 pr-6 font-medium text-text-secondary">Ügyfél</th>
            <th className="py-1.5 pr-6 font-medium text-text-secondary">Cég</th>
            <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Végösszeg</th>
            <th className="py-1.5 pr-6 font-medium text-text-secondary">Módosítva</th>
            <th className="py-1.5 text-right font-medium text-text-secondary"></th>
          </tr>
        </thead>
        <tbody>
          {[...sorok]
            .sort((a, b) => b.id - a.id)
            .map((a) => (
              <tr key={a.id} className="border-b border-border last:border-0">
                <td className="py-2.5 pr-6">
                  <button
                    type="button"
                    disabled={busyId === a.id}
                    onClick={() => onMegnyitas(a.id)}
                    className="text-left text-text-accent hover:underline disabled:opacity-50"
                  >
                    {a.nev}
                  </button>
                </td>
                <td className="py-2.5 pr-6 text-text-secondary">{a.ugyfel ?? "–"}</td>
                <td className="py-2.5 pr-6">
                  <StatusBadge
                    label={(BRAND_BEALLITAS[a.brand] ?? BRAND_BEALLITAS.hype).nev}
                    tone={a.brand === "contentbee" ? "warning" : "neutral"}
                  />
                </td>
                <td className="py-2.5 pr-6 text-right font-mono text-[12.5px]">
                  {a.vegosszeg !== null ? `${osszegSzoveg(a.vegosszeg)} Ft` : "–"}
                </td>
                <td className="py-2.5 pr-6 text-text-muted">
                  {a.updated_at ? a.updated_at.slice(0, 10) : "–"}
                </td>
                <td className="py-2.5 text-right">
                  {onTorles && (
                    <button
                      type="button"
                      disabled={busyId === a.id}
                      onClick={() => onTorles(a)}
                      className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                      title="Törlés"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

/** Az ALAP TÉTELEK katalógusa - amit a szerkesztő "Alap tételek" panelje
 * kínál fel egy kattintásra (a felhasználó kérése). Egyszerű, helyben
 * szerkeszthető lista. */
function TetelKatalogus({
  tetelek,
  canEdit,
  canDelete,
}: {
  tetelek: ArajanlatTetel[];
  canEdit: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const [uj, setUj] = useState({ nev: "", megjegyzes: "", szekcio: "", egysegar: "" });
  const [busy, setBusy] = useState(false);

  async function hozzaadas() {
    if (!uj.nev.trim()) return;
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/arajanlat-tetelek", {
        method: "POST",
        body: JSON.stringify({
          nev: uj.nev.trim(),
          megjegyzes: uj.megjegyzes.trim() || null,
          szekcio: uj.szekcio.trim() || null,
          egysegar: uj.egysegar.trim() ? Number(uj.egysegar.replace(/[^\d.,-]/g, "").replace(",", ".")) : null,
        }),
      });
      if (!res.ok) {
        alert(`Nem sikerült felvenni (HTTP ${res.status}).`);
        return;
      }
      setUj({ nev: "", megjegyzes: "", szekcio: "", egysegar: "" });
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function torles(t: ArajanlatTetel) {
    if (!window.confirm(`Törlöd a katalógusból: ${t.nev}?`)) return;
    setBusy(true);
    try {
      await authFetch(`/api/v1/arajanlat-tetelek/${t.id}`, { method: "DELETE" });
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Alap tételek (katalógus)">
      <p className="mb-3 text-[12.5px] text-text-muted">
        Ezek a tételek a szerkesztő „Alap tételek” paneljéből egy kattintással kerülnek az ajánlatba – a
        szekció mondja meg, hova (Technika, Utómunka, Emberi erőforrás…).
      </p>
      {canEdit && (
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Tétel neve *
            <input className="field min-w-[180px]" value={uj.nev} onChange={(e) => setUj({ ...uj, nev: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Megjegyzés
            <input className="field min-w-[220px]" value={uj.megjegyzes} onChange={(e) => setUj({ ...uj, megjegyzes: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Szekció
            <input
              className="field min-w-[140px]"
              value={uj.szekcio}
              onChange={(e) => setUj({ ...uj, szekcio: e.target.value })}
              placeholder="pl. Technika"
              list="aj-szekcio-javaslatok"
            />
            <datalist id="aj-szekcio-javaslatok">
              {[...new Set(tetelek.map((t) => t.szekcio).filter(Boolean))].map((sz) => (
                <option key={sz as string} value={sz as string} />
              ))}
            </datalist>
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-text-muted">
            Egységár (Ft)
            <input className="field w-[120px]" inputMode="decimal" value={uj.egysegar} onChange={(e) => setUj({ ...uj, egysegar: e.target.value })} />
          </label>
          <button type="button" disabled={busy || !uj.nev.trim()} onClick={hozzaadas} className="btn btn-primary text-[13px]">
            + Felvétel
          </button>
        </div>
      )}
      {tetelek.length === 0 ? (
        <p className="text-[13px] text-text-secondary">Még nincs alap tétel.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="py-1.5 pr-6 font-medium text-text-secondary">Tétel</th>
                <th className="py-1.5 pr-6 font-medium text-text-secondary">Megjegyzés</th>
                <th className="py-1.5 pr-6 font-medium text-text-secondary">Szekció</th>
                <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Egységár</th>
                <th className="py-1.5 text-right font-medium text-text-secondary"></th>
              </tr>
            </thead>
            <tbody>
              {[...tetelek]
                .sort((a, b) => (a.szekcio ?? "").localeCompare(b.szekcio ?? "", "hu") || a.nev.localeCompare(b.nev, "hu"))
                .map((t) => (
                  <tr key={t.id} className="border-b border-border last:border-0">
                    <td className="py-2 pr-6">{t.nev}</td>
                    <td className="py-2 pr-6 text-text-secondary">{t.megjegyzes ?? "–"}</td>
                    <td className="py-2 pr-6 text-text-secondary">{t.szekcio ?? "–"}</td>
                    <td className="py-2 pr-6 text-right font-mono text-[12.5px]">
                      {t.egysegar !== null ? `${osszegSzoveg(t.egysegar)} Ft` : "–"}
                    </td>
                    <td className="py-2 text-right">
                      {canDelete && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => torles(t)}
                          className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                          title="Törlés"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
