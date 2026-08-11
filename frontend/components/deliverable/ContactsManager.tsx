"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Copy } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { vagolapra } from "@/lib/vagolap";
import type { DeliverableContact, MegrendeloiKontakt } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

/** "Megrendelői kontaktok" - kiknek kell majd kiküldeni a kész anyagot (a
 * megrendeloi_email_cimek formula-mező ebből számolódik újra, lásd
 * services/deliverable_actions.set_contacts).
 *
 * A választék az ÖSSZES megrendelői kontakt, nem csak az anyag ügyfeléé: egy
 * kész anyagot gyakran olyanoknak is ki kell küldeni, akik máshol vannak
 * (ügynökség, társproducer). Az anyag saját ügyfelének kontaktjai kerülnek a
 * lista elejére, mert azok a gyakoriak. */
export function ContactsManager({
  deliverableId,
  current,
  options,
  clientId,
}: {
  deliverableId: number;
  current: DeliverableContact[];
  options: MegrendeloiKontakt[];
  /** Az anyag ügyfele - az ő kontaktjait ajánljuk fel elöl. */
  clientId?: number | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [kereses, setKereses] = useState("");
  const [masolasUzenet, setMasolasUzenet] = useState<string | null>(null);

  const currentIds = current.map((c) => c.id);
  const emailek = useMemo(
    () => Array.from(new Set(current.map((c) => (c.email ?? "").trim()).filter(Boolean))),
    [current],
  );

  const valaszthato = useMemo(() => {
    const q = kereses.trim().toLowerCase();
    const szurt = options
      .filter((o) => !currentIds.includes(o.id))
      .filter((o) =>
        !q ? true : [o.full_name, o.email, o.client_nev].some((m) => (m ?? "").toLowerCase().includes(q)),
      );
    // Az anyag saját ügyfelének kontaktjai elöl, utána a többi - mindkét
    // csoporton belül név szerint.
    return szurt.sort((a, b) => {
      const sajatA = clientId != null && a.client_id === clientId ? 0 : 1;
      const sajatB = clientId != null && b.client_id === clientId ? 0 : 1;
      if (sajatA !== sajatB) return sajatA - sajatB;
      return a.full_name.localeCompare(b.full_name, "hu");
    });
  }, [options, currentIds, kereses, clientId]);

  async function save(ids: number[]) {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/contacts`, {
        method: "PUT",
        body: JSON.stringify({ contact_ids: ids }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function emaileketMasol() {
    if (emailek.length === 0) {
      setMasolasUzenet("A hozzáadott kontaktoknak nincs email címe.");
      return;
    }
    const sikeres = await vagolapra(emailek.join(", "));
    setMasolasUzenet(
      sikeres
        ? `${emailek.length} email cím a vágólapon.`
        : "A böngésző nem engedte a másolást – jelöld ki és másold kézzel.",
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {current.length === 0 && <p className="text-[13px] text-text-muted">Nincs megrendelői kontakt hozzárendelve.</p>}
        {current.map((c) => (
          <span key={c.id} className="flex items-center gap-1.5 rounded-[var(--radius)] bg-surface-3 px-2.5 py-1 text-[13px]">
            {c.full_name}
            {c.email && <span className="text-text-muted">({c.email})</span>}
            <button
              type="button"
              disabled={busy}
              onClick={() => save(currentIds.filter((id) => id !== c.id))}
              className="text-text-muted hover:text-text-danger disabled:opacity-50"
              title="Leválasztás"
            >
              ✕
            </button>
          </span>
        ))}
      </div>

      {/* A gomb, amivel a kiküldés tényleg elkezdhető: az összes hozzáadott
          kontakt email címe egyben, vesszővel elválasztva - ahogy egy levél
          címzett-mezőjébe kell. */}
      {current.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={emaileketMasol}
            className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
            title="Az összes hozzáadott kontakt email címe, vesszővel elválasztva"
          >
            <Copy size={13} /> Email címek másolása ({emailek.length})
          </button>
          {masolasUzenet && <span className="text-[12px] text-text-accent">{masolasUzenet}</span>}
        </div>
      )}

      {options.length === 0 ? (
        <p className="text-[12px] text-text-muted">
          Még nincs felvéve megrendelői kontakt (Ügyfelek → Megrendelői kontaktok).
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {/* Kereshető lista: több száz kontaktnál egy sima legördülőben nem
              lehetne megtalálni valakit. */}
          <input
            value={kereses}
            onChange={(e) => setKereses(e.target.value)}
            placeholder="Keresés név, email, ügyfél szerint…"
            className="w-[260px] rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
          <KeresosSelect
            value={null}
            options={valaszthato.map((o) => ({
              value: String(o.id),
              label: `${o.full_name}${o.client_nev ? ` – ${o.client_nev}` : ""}`,
              sublabel: o.email ?? undefined,
            }))}
            onChange={(ertek) => {
              save([...currentIds, Number(ertek)]);
              setKereses("");
            }}
            disabled={busy || valaszthato.length === 0}
            placeholder={valaszthato.length === 0 ? "Nincs találat" : `Hozzáadás… (${valaszthato.length})`}
            className="max-w-[420px]"
          />
        </div>
      )}
    </div>
  );
}
