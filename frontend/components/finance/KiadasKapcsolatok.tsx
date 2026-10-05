"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Pencil, X } from "lucide-react";
import { KeresosSelect, type KeresosOpcio } from "@/components/KeresosSelect";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";

type Mezo = "project_code_id" | "employee_id";

/** A kiadás PROJEKTKÓDJA és ALVÁLLALKOZÓJA az adatlapon: hozzáadható,
 * cserélhető és - a felhasználó kérése szerint - LEVEHETŐ.
 *
 * A levétel a háttérben a forgatás-hozzárendelést is kiszedi (lásd backend
 * routes/finance._expense_before_update): a levett alvállalkozó így nem marad
 * ott az Utókövetésben szerződés/TIG-teendőként. A már elkészült szerződés
 * vagy TIG ettől nem törlődik - az a saját helyén kezelendő. */
export function KiadasKapcsolatok({
  expenseId,
  projectCode,
  employee,
  projektkodOpciok,
  emberOpciok,
  canEdit,
}: {
  expenseId: number;
  projectCode: { id: number; projektkod: string; nev: string | null } | null;
  employee: { id: number; nev: string } | null;
  projektkodOpciok: KeresosOpcio[];
  emberOpciok: KeresosOpcio[];
  canEdit: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [szerkeszt, setSzerkeszt] = useState<Mezo | null>(null);
  const [busy, setBusy] = useState<Mezo | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  async function ment(mezo: Mezo, ertek: number | null) {
    setBusy(mezo);
    setHiba(null);
    try {
      // Új alvállalkozó hozzáadásakor a besorolás "Külsős" lesz, ahogy a
      // felvivő űrlapon is (szerződés/TIG csak a külsős tétel emberéről jár).
      const body: Record<string, unknown> = { [mezo]: ertek };
      if (mezo === "employee_id" && ertek !== null) body.tipus = "kulsos";
      const res = await authFetch(`/api/v1/expenses/${expenseId}`, { method: "PATCH", body: JSON.stringify(body) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(`Nem sikerült menteni: ${detail?.detail ?? res.status}`);
        return;
      }
      setSzerkeszt(null);
      router.refresh();
    } catch (err) {
      setHiba(`Nem sikerült menteni (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  async function levesz(mezo: Mezo) {
    const ok = await confirm(
      mezo === "project_code_id"
        ? `Leveszed a(z) ${projectCode?.projektkod ?? ""} projektkódot erről a kiadásról? A tétel ezután nem jelenik meg a projektkód kiadásai között.`
        : `Leveszed ${employee?.nev ?? ""} alvállalkozót erről a kiadásról? Ha emiatt szerepelt az Utókövetésben, onnan is eltűnik (a már elkészült szerződés vagy TIG megmarad).`,
      { megerositoCimke: "Levétel" },
    );
    if (ok) await ment(mezo, null);
  }

  function sor(
    mezo: Mezo,
    cim: string,
    aktualis: { href: string; felirat: string; alcim?: string | null } | null,
    opciok: KeresosOpcio[],
    hozzaadCimke: string,
  ) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
        <span className="w-32 shrink-0 text-[12.5px] text-text-secondary">{cim}</span>
        {szerkeszt === mezo ? (
          <span className="flex items-center gap-2">
            <KeresosSelect
              value={null}
              options={opciok}
              onChange={(v) => v && void ment(mezo, Number(v))}
              placeholder={busy === mezo ? "Mentés…" : "Válassz…"}
              disabled={busy === mezo}
              className="min-w-[240px]"
            />
            <button
              type="button"
              onClick={() => setSzerkeszt(null)}
              className="text-[12px] text-text-muted hover:text-text-primary"
            >
              Mégse
            </button>
          </span>
        ) : aktualis ? (
          <span className="flex flex-wrap items-center gap-2 text-[13px]">
            <Link href={aktualis.href} className="text-text-accent hover:underline">
              {aktualis.felirat}
            </Link>
            {aktualis.alcim && <span className="text-[12px] text-text-muted">{aktualis.alcim}</span>}
            {canEdit && (
              <>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => setSzerkeszt(mezo)}
                  title={`${cim} cseréje`}
                  aria-label={`${cim} cseréje`}
                  className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-primary disabled:opacity-50"
                >
                  <Pencil size={12} />
                </button>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void levesz(mezo)}
                  className="inline-flex items-center gap-1 rounded-[var(--radius)] px-1.5 py-0.5 text-[12px] text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                >
                  <X size={12} />
                  Levétel
                </button>
              </>
            )}
          </span>
        ) : canEdit ? (
          <button
            type="button"
            onClick={() => setSzerkeszt(mezo)}
            className="text-[13px] text-text-accent hover:underline"
          >
            {hozzaadCimke}
          </button>
        ) : (
          <span className="text-[13px] text-text-muted">–</span>
        )}
      </div>
    );
  }

  return (
    <div className="divide-y divide-border">
      {sor(
        "project_code_id",
        "Projektkód",
        projectCode
          ? { href: `/projektek/project-kodok/${projectCode.id}`, felirat: projectCode.projektkod, alcim: projectCode.nev }
          : null,
        projektkodOpciok,
        "+ Projektkódhoz rendelés",
      )}
      {sor(
        "employee_id",
        "Alvállalkozó",
        employee ? { href: `/csapat/${employee.id}`, felirat: employee.nev } : null,
        emberOpciok,
        "+ Alvállalkozó hozzáadása",
      )}
      {hiba && <p className="pt-2 text-[12px] text-text-danger">{hiba}</p>}
    </div>
  );
}
