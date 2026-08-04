"use client";

import { useEffect, useState } from "react";
import { Plus, RotateCcw, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { SelectDropdown } from "@/components/SelectDropdown";
import { authFetch } from "@/lib/authFetch";
import { humanizeKey } from "@/lib/mezoNev";
import type { EntityField } from "@/lib/api";

const TIPUS_LABELS: Record<string, string> = {
  text: "Szöveg",
  number: "Szám",
  boolean: "Igen / Nem",
  date: "Dátum",
  datetime: "Dátum + idő",
  time: "Időpont",
  select: "Legördülő",
};
const UJ_MEZO_TIPUSOK = ["text", "number", "boolean", "date", "datetime", "select"];

/** Mezők kezelése entitásonként: a Notionből áthozott, itt már felesleges
 * mezők eltávolítása (adattörléssel vagy anélkül), a korábban eltávolítottak
 * visszahozása, és saját mezők létrehozása.
 *
 * Az eltávolított mező az EGÉSZ rendszerből eltűnik (adatlap, listák,
 * mezőtípusok, szerkesztés) - nem csak egy felhasználótól, arra a
 * mező-láthatóság beállítás való. A saját mező azonnal megjelenik a rekordok
 * adatlapján, és ugyanúgy szerkeszthető, mint bármelyik eredeti mező. */
export function EntityFieldManager({
  entities,
}: {
  entities: { entityType: string; label: string }[];
}) {
  const confirm = useConfirm();
  const [entityType, setEntityType] = useState(entities[0]?.entityType ?? "");
  const [fields, setFields] = useState<EntityField[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [ujNyitva, setUjNyitva] = useState(false);
  const [uj, setUj] = useState({ field_key: "", label: "", field_type: "text", options: "" });
  const [szuro, setSzuro] = useState("");

  useEffect(() => {
    if (!entityType) return;
    let elavult = false;
    // Az entitás váltásakor újratöltjük a mezőlistát. A state-et szándékosan
    // csak ezen a betöltő függvényen belül állítjuk (nem közvetlenül az effect
    // törzsében), különben minden váltás felesleges extra rendert okozna.
    const betolt = async () => {
      setLoading(true);
      setHiba(null);
      try {
        const res = await authFetch(`/api/v1/entity-fields/${entityType}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { fields: EntityField[] };
        if (!elavult) setFields(data.fields);
      } catch (err) {
        if (!elavult) setHiba(String(err));
      } finally {
        if (!elavult) setLoading(false);
      }
    };
    void betolt();
    return () => {
      elavult = true;
    };
  }, [entityType]);

  async function ujratolt() {
    const res = await authFetch(`/api/v1/entity-fields/${entityType}`);
    if (res.ok) setFields(((await res.json()) as { fields: EntityField[] }).fields);
  }

  async function hivas(path: string, init: RequestInit): Promise<boolean> {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(path, init);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen művelet (HTTP ${res.status})`);
        return false;
      }
      await ujratolt();
      return true;
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function eltavolit(mezo: EntityField) {
    const adattal = await confirm(
      `Eltávolítod a(z) "${humanizeKey(mezo.name)}" mezőt? Eltűnik az egész rendszerből. ` +
        `Az OK-ra kattintva a mezőben tárolt ADATOKAT IS VÉGLEG TÖRÖLJÜK.`,
    );
    if (!adattal) return;
    await hivas(`/api/v1/entity-fields/${entityType}/remove`, {
      method: "POST",
      body: JSON.stringify({ field_name: mezo.name, wipe_data: true }),
    });
  }

  async function elrejt(mezo: EntityField) {
    await hivas(`/api/v1/entity-fields/${entityType}/remove`, {
      method: "POST",
      body: JSON.stringify({ field_name: mezo.name, wipe_data: false }),
    });
  }

  async function visszaallit(mezo: EntityField) {
    await hivas(`/api/v1/entity-fields/${entityType}/restore`, {
      method: "POST",
      body: JSON.stringify({ field_name: mezo.name }),
    });
  }

  async function sajatTorles(mezo: EntityField) {
    if (
      !(await confirm(
        `Véglegesen törlöd a(z) "${mezo.label}" saját mezőt? Az összes rekordon tárolt értéke is elveszik.`,
      ))
    )
      return;
    await hivas(`/api/v1/entity-fields/${entityType}/custom/${mezo.name}`, { method: "DELETE" });
  }

  async function ujMezo() {
    const options = uj.options
      .split(",")
      .map((o) => o.trim())
      .filter(Boolean);
    const sikeres = await hivas(`/api/v1/entity-fields/${entityType}/custom`, {
      method: "POST",
      body: JSON.stringify({
        field_key: uj.field_key.trim(),
        label: uj.label.trim() || uj.field_key.trim(),
        field_type: uj.field_type,
        options: uj.field_type === "select" ? options : null,
      }),
    });
    if (sikeres) {
      setUj({ field_key: "", label: "", field_type: "text", options: "" });
      setUjNyitva(false);
    }
  }

  const kereses = szuro.trim().toLowerCase();
  const szurt = kereses
    ? fields.filter((f) => f.name.toLowerCase().includes(kereses) || f.label.toLowerCase().includes(kereses))
    : fields;
  const aktivak = szurt.filter((f) => !f.removed);
  const eltavolitottak = szurt.filter((f) => f.removed);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <SelectDropdown
          value={entities.find((e) => e.entityType === entityType)?.label ?? null}
          options={entities.map((e) => e.label)}
          onChange={(label) => {
            const talalat = entities.find((e) => e.label === label);
            if (talalat) setEntityType(talalat.entityType);
          }}
          placeholder="Válassz entitást"
        />
        <input
          value={szuro}
          onChange={(e) => setSzuro(e.target.value)}
          placeholder="Mező keresése…"
          className="w-52 rounded-[var(--radius)] border border-border bg-surface-1 px-2.5 py-1.5 text-[13px] text-text-primary outline-none focus:border-text-accent"
        />
        <button
          type="button"
          onClick={() => setUjNyitva((o) => !o)}
          className="ml-auto flex items-center gap-1 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent"
        >
          <Plus size={13} /> Új mező
        </button>
      </div>

      {ujNyitva && (
        <div className="mb-4 rounded-[var(--radius)] border border-border bg-surface-1 p-3">
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-[12px] text-text-secondary">
              Azonosító
              <input
                value={uj.field_key}
                onChange={(e) => setUj({ ...uj, field_key: e.target.value })}
                placeholder="pl. polo_meret"
                className="mt-1 block w-44 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary outline-none focus:border-text-accent"
              />
            </label>
            <label className="text-[12px] text-text-secondary">
              Megnevezés
              <input
                value={uj.label}
                onChange={(e) => setUj({ ...uj, label: e.target.value })}
                placeholder="pl. Póló méret"
                className="mt-1 block w-52 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary outline-none focus:border-text-accent"
              />
            </label>
            {/* Szándékosan NEM <label>: a SelectDropdown egy gombot renderel,
                egy <label>-be ágyazott gombra pedig a címke szövegére
                kattintva is rákattintanánk (és a képernyőolvasók sem tudják
                értelmesen megnevezni). */}
            <div className="text-[12px] text-text-secondary">
              Típus
              <span className="mt-1 block">
                <SelectDropdown
                  value={TIPUS_LABELS[uj.field_type] ?? uj.field_type}
                  options={UJ_MEZO_TIPUSOK.map((t) => TIPUS_LABELS[t])}
                  onChange={(label) => {
                    const tipus = UJ_MEZO_TIPUSOK.find((t) => TIPUS_LABELS[t] === label);
                    if (tipus) setUj({ ...uj, field_type: tipus });
                  }}
                  placeholder="Típus"
                />
              </span>
            </div>
            {uj.field_type === "select" && (
              <label className="text-[12px] text-text-secondary">
                Választható értékek (vesszővel)
                <input
                  value={uj.options}
                  onChange={(e) => setUj({ ...uj, options: e.target.value })}
                  placeholder="S, M, L, XL"
                  className="mt-1 block w-60 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary outline-none focus:border-text-accent"
                />
              </label>
            )}
            <button
              type="button"
              disabled={busy || !uj.field_key.trim()}
              onClick={ujMezo}
              className="rounded-[var(--radius)] bg-bg-success px-3 py-1.5 text-[13px] font-medium text-text-success disabled:opacity-50"
            >
              Létrehozás
            </button>
          </div>
          <p className="mt-2 text-[11px] text-text-muted">
            Az új mező azonnal megjelenik a rekordok adatlapján, és ugyanúgy szerkeszthető, mint bármelyik eredeti mező.
          </p>
        </div>
      )}

      {hiba && <p className="mb-3 text-[13px] text-text-danger">{hiba}</p>}
      {loading && <p className="text-[13px] text-text-muted">Betöltés…</p>}

      {!loading && (
        <>
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border">
                <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Mező</th>
                <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Azonosító</th>
                <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Típus</th>
                <th className="py-1.5 text-right font-medium text-text-secondary">Művelet</th>
              </tr>
            </thead>
            <tbody>
              {aktivak.map((mezo) => (
                <tr key={mezo.name} className="border-b border-border last:border-0">
                  <td className="py-2 pr-4 text-text-primary">
                    {mezo.custom ? mezo.label : humanizeKey(mezo.name)}
                    {mezo.custom && (
                      <span className="ml-2 rounded-full bg-bg-accent px-1.5 py-0.5 text-[10px] text-text-accent">saját</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 font-mono text-[12px] text-text-muted">{mezo.name}</td>
                  <td className="py-2 pr-4 text-text-secondary">{TIPUS_LABELS[mezo.type] ?? mezo.type}</td>
                  <td className="py-2 text-right whitespace-nowrap">
                    {mezo.custom ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => sajatTorles(mezo)}
                        className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                        title="Saját mező végleges törlése"
                      >
                        <Trash2 size={13} />
                      </button>
                    ) : mezo.removable ? (
                      <>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => elrejt(mezo)}
                          className="mr-1 rounded-[var(--radius)] border border-border px-2 py-0.5 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                          title="A mező eltűnik a rendszerből, de az adata megmarad (visszahozható)"
                        >
                          Eltávolítás
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => eltavolit(mezo)}
                          className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                          title="Eltávolítás az adatok végleges törlésével"
                        >
                          <Trash2 size={13} />
                        </button>
                      </>
                    ) : (
                      <span className="text-[12px] text-text-muted">{mezo.reason}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {eltavolitottak.length > 0 && (
            <div className="mt-5">
              <p className="mb-2 text-[12px] font-medium text-text-secondary">
                Eltávolított mezők ({eltavolitottak.length})
              </p>
              <div className="flex flex-wrap gap-2">
                {eltavolitottak.map((mezo) => (
                  <span
                    key={mezo.name}
                    className="flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[12px] text-text-muted"
                  >
                    {humanizeKey(mezo.name)}
                    {mezo.data_wiped && <span className="text-text-danger">· adat törölve</span>}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => visszaallit(mezo)}
                      className="text-text-accent hover:underline disabled:opacity-50"
                      title="Mező visszahozása"
                    >
                      <RotateCcw size={12} />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
