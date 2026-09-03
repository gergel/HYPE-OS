"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil } from "lucide-react";
import { KeresosSelect } from "@/components/KeresosSelect";
import { authFetch } from "@/lib/authFetch";

/** A kiadás PROJEKTKÓD-cellája a Pénzügyek → Kiadások listában (a felhasználó
 * kérése): látszik, melyik projektkódra terhel a tétel, és utólag is
 * hozzárendelhető/átrendelhető - kereshető legördülőből. A hozzárendelt
 * kiadás automatikusan megjelenik a projektkód adatlapjának kiadásai közt is
 * (ugyanaz a rekord, lásd backend services/projektkod_bontas.py). */
export function KiadasProjektkodCella({
  expenseId,
  projectCodeId,
  opciok,
  canEdit,
}: {
  expenseId: number;
  projectCodeId: number | null;
  opciok: { id: number; projektkod: string; nev: string | null }[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const [szerkeszt, setSzerkeszt] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState(false);
  const aktualis = opciok.find((o) => o.id === projectCodeId) ?? null;

  async function valaszt(next: string) {
    if (busy) return;
    setBusy(true);
    setHiba(false);
    try {
      const res = await authFetch(`/api/v1/expenses/${expenseId}`, {
        method: "PATCH",
        body: JSON.stringify({ project_code_id: next ? Number(next) : null }),
      });
      if (!res.ok) {
        setHiba(true);
        return;
      }
      setSzerkeszt(false);
      router.refresh();
    } catch {
      setHiba(true);
    } finally {
      setBusy(false);
    }
  }

  // A cellára kattintás ne nyissa meg a sor adatlapját (a DataTable sora
  // kattintható) - ugyanaz a minta, mint a lista Állapot oszlopánál.
  return (
    <span onClick={(e) => e.stopPropagation()}>
      {szerkeszt ? (
        <KeresosSelect
          value={projectCodeId !== null ? String(projectCodeId) : null}
          options={[
            { value: "", label: "Nincs projektkód" },
            ...opciok.map((o) => ({
              value: String(o.id),
              label: o.projektkod,
              sublabel: o.nev ?? undefined,
            })),
          ]}
          onChange={(next) => void valaszt(next)}
          placeholder={busy ? "Mentés…" : "Válassz projektkódot…"}
          disabled={busy}
          className="min-w-[180px]"
        />
      ) : (
        <button
          type="button"
          disabled={!canEdit}
          onClick={() => canEdit && setSzerkeszt(true)}
          className={`inline-flex items-center gap-1.5 text-left text-[13px] ${
            canEdit ? "hover:underline" : "cursor-default"
          } ${aktualis ? "text-text-primary" : "text-text-muted"}`}
          title={canEdit ? "Projektkódhoz rendelés" : undefined}
        >
          {aktualis ? (
            <span>
              {aktualis.projektkod}
              {aktualis.nev && <span className="ml-1 text-[12px] text-text-muted">({aktualis.nev})</span>}
            </span>
          ) : (
            <span>{canEdit ? "+ Projektkódhoz" : "–"}</span>
          )}
          {canEdit && <Pencil size={11} className="shrink-0 text-text-muted" />}
        </button>
      )}
      {hiba && <span className="block text-[11.5px] text-text-danger">Nem sikerült menteni.</span>}
    </span>
  );
}
