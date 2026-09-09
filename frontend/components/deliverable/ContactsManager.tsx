"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Copy } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { vagolapra } from "@/lib/vagolap";
import { vedettOverlayZaras } from "@/lib/vedettOverlayZaras";
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
  ugyfelek = [],
}: {
  deliverableId: number;
  current: DeliverableContact[];
  options: MegrendeloiKontakt[];
  /** Az anyag ügyfele - az ő kontaktjait ajánljuk fel elöl. */
  clientId?: number | null;
  /** Az ügyfelek listája az ÚJ kontakt felvételéhez (a felhasználó kérése:
   * ha valaki nincs a kontaktok közt, innen, helyben is felvehető legyen). */
  ugyfelek?: { id: number; nev: string }[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [kereses, setKereses] = useState("");
  const [masolasUzenet, setMasolasUzenet] = useState<string | null>(null);
  // ÚJ kontakt felvétele helyben (a felhasználó kérése): a kereső "hozzáadása
  // újként" sorából nyílik, a beírt névvel előtöltve - mentés után rögtön az
  // anyaghoz is hozzákapcsoljuk.
  const [ujKontakt, setUjKontakt] = useState<{ full_name: string; email: string; phone: string; client_id: string } | null>(
    null,
  );

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

  /** Az új kontakt mentése (POST /contacts, mint az Ügyfelek oldali űrlap),
   * majd azonnal hozzákapcsolás az anyaghoz - a felhasználónak nem kell
   * külön megkeresnie, akit épp most vett fel. */
  async function ujKontaktMentes() {
    if (!ujKontakt) return;
    if (!ujKontakt.full_name.trim()) {
      alert("Add meg a kontakt nevét.");
      return;
    }
    if (!ujKontakt.client_id) {
      alert("Válaszd ki, melyik ügyfélhez tartozik a kontakt.");
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/contacts", {
        method: "POST",
        body: JSON.stringify({
          full_name: ujKontakt.full_name.trim(),
          email: ujKontakt.email.trim() || null,
          phone: ujKontakt.phone.trim() || null,
          client_id: Number(ujKontakt.client_id),
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`A kontakt felvétele nem sikerült: ${detail?.detail ?? res.status}`);
        return;
      }
      const letrehozott = (await res.json()) as { id: number };
      setUjKontakt(null);
      setKereses("");
      await save([...currentIds, letrehozott.id]);
    } catch (err) {
      alert(`A kontakt felvétele nem sikerült (hálózati hiba): ${err}`);
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
          // Üres választéknál sincs letiltva (a felhasználó kérése): a beírt
          // névvel ÚJ kontakt vehető fel a lenti "hozzáadása újként" sorral.
          disabled={busy}
          placeholder={valaszthato.length === 0 ? "Új kontakt felvétele…" : `Hozzáadás… (${valaszthato.length})`}
          className="max-w-[420px]"
          // ÚJ kontakt felvétele a keresőből (a felhasználó kérése): ha
          // valaki nincs a listában, a beírt névvel helyben felvehető.
          onUjFelvetel={(beirtNev) =>
            setUjKontakt({
              full_name: beirtNev,
              email: "",
              phone: "",
              client_id: clientId != null ? String(clientId) : "",
            })
          }
        />
      </div>

      {/* ÚJ KONTAKT felugró űrlapja - ugyanazok a mezők, mint az Ügyfelek →
          Megrendelői kontaktok oldalon; az ügyfél az anyagéval előtöltve. */}
      {ujKontakt && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
          {...vedettOverlayZaras(() => !busy && setUjKontakt(null))}
        >
          <div
            className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-[15px] font-medium text-text-primary">Új megrendelői kontakt</h3>
            <div className="grid grid-cols-1 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Név *</label>
                <input
                  value={ujKontakt.full_name}
                  onChange={(e) => setUjKontakt({ ...ujKontakt, full_name: e.target.value })}
                  autoFocus
                  className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Ügyfél *</label>
                <KeresosSelect
                  value={ujKontakt.client_id || null}
                  options={ugyfelek.map((u) => ({ value: String(u.id), label: u.nev }))}
                  onChange={(ertek) => setUjKontakt({ ...ujKontakt, client_id: ertek })}
                  placeholder="Válassz ügyfelet…"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Email</label>
                <input
                  type="email"
                  value={ujKontakt.email}
                  onChange={(e) => setUjKontakt({ ...ujKontakt, email: e.target.value })}
                  className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Telefon</label>
                <input
                  value={ujKontakt.phone}
                  onChange={(e) => setUjKontakt({ ...ujKontakt, phone: e.target.value })}
                  className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
                />
              </div>
            </div>
            <div className="mt-5 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setUjKontakt(null)}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={() => void ujKontaktMentes()}
                disabled={busy}
                className="rounded-[var(--radius)] bg-[var(--accent-solid)] px-4 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-60"
              >
                {busy ? "Mentés…" : "Felvétel és hozzáadás"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
