"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { ModalReteg } from "@/components/ModalReteg";
import { authFetch } from "@/lib/authFetch";
import { vagolapra } from "@/lib/vagolap";
import type { MegrendeloiKontakt } from "@/lib/api";

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

type Urlap = {
  full_name: string;
  email: string;
  phone: string;
  client_id: string;
};

/** Az összes megrendelői kontakt egy listában, kereséssel.
 *
 * A gomb, ami miatt ez az oldal létezik: a SZŰRT lista összes email címét
 * egyben a vágólapra teszi - pontosan azt, ami egy levél címzett-mezőjébe
 * kell, nem kell egyenként kimásolgatni. */
export function KontaktLista({
  kontaktok,
  ugyfelek,
  canEdit,
  canCreate,
  canDelete,
}: {
  kontaktok: MegrendeloiKontakt[];
  ugyfelek: { id: number; nev: string }[];
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [kereses, setKereses] = useState("");
  const [urlap, setUrlap] = useState<Urlap | null>(null);
  const [szerkesztettId, setSzerkesztettId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [masolasUzenet, setMasolasUzenet] = useState<string | null>(null);

  const szurt = useMemo(() => {
    const q = kereses.trim().toLowerCase();
    if (!q) return kontaktok;
    return kontaktok.filter((k) =>
      [k.full_name, k.email, k.phone, k.client_nev].some((mezo) => (mezo ?? "").toLowerCase().includes(q)),
    );
  }, [kontaktok, kereses]);

  const emailek = useMemo(
    () => Array.from(new Set(szurt.map((k) => (k.email ?? "").trim()).filter(Boolean))),
    [szurt],
  );

  async function emaileketMasol() {
    if (emailek.length === 0) {
      setMasolasUzenet("Ezekhez a kontaktokhoz nincs email cím.");
      return;
    }
    const sikeres = await vagolapra(emailek.join(", "));
    setMasolasUzenet(
      sikeres
        ? `${emailek.length} email cím a vágólapon.`
        : "A böngésző nem engedte a másolást – jelöld ki és másold kézzel.",
    );
  }

  function ujat() {
    setSzerkesztettId(null);
    setUrlap({ full_name: "", email: "", phone: "", client_id: ugyfelek[0] ? String(ugyfelek[0].id) : "" });
  }

  function szerkeszt(k: MegrendeloiKontakt) {
    setSzerkesztettId(k.id);
    setUrlap({
      full_name: k.full_name,
      email: k.email ?? "",
      phone: k.phone ?? "",
      client_id: String(k.client_id),
    });
  }

  async function ment() {
    if (!urlap) return;
    if (!urlap.full_name.trim()) {
      alert("A név kötelező.");
      return;
    }
    if (!urlap.client_id) {
      alert("Válaszd ki, melyik ügyfélhez tartozik.");
      return;
    }
    setBusy(true);
    try {
      // A kontaktok adatát a meglévő /contacts CRUD kezeli - ez az oldal csak
      // egy másik nézet ugyanarra az adatra.
      const res = await authFetch(szerkesztettId ? `/api/v1/contacts/${szerkesztettId}` : "/api/v1/contacts", {
        method: szerkesztettId ? "PATCH" : "POST",
        body: JSON.stringify({
          full_name: urlap.full_name.trim(),
          email: urlap.email.trim() || null,
          phone: urlap.phone.trim() || null,
          ...(szerkesztettId ? {} : { client_id: Number(urlap.client_id) }),
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setUrlap(null);
      setSzerkesztettId(null);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function torol(k: MegrendeloiKontakt) {
    const figyelmeztetes =
      k.anyagok_szama > 0
        ? ` ${k.anyagok_szama} anyagnál van beállítva, hogy neki is ki kell küldeni – onnan is eltűnik.`
        : "";
    if (!(await confirm(`Törlöd ezt a kontaktot: "${k.full_name}"?${figyelmeztetes}`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/contacts/${k.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={kereses}
          onChange={(e) => {
            setKereses(e.target.value);
            setMasolasUzenet(null);
          }}
          placeholder="Keresés név, email, ügyfél szerint…"
          className={`${inputClass} max-w-[320px]`}
        />
        <button
          type="button"
          onClick={emaileketMasol}
          className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          title="A most látható kontaktok email címei, vesszővel elválasztva"
        >
          <Copy size={13} />
          {kereses.trim() ? `Szűrt lista email címei (${emailek.length})` : `Összes email cím (${emailek.length})`}
        </button>
        <span className="text-[12px] text-text-muted">
          {szurt.length === kontaktok.length ? `${kontaktok.length} kontakt` : `${szurt.length} / ${kontaktok.length} kontakt`}
        </span>
        {masolasUzenet && <span className="text-[12px] text-text-accent">{masolasUzenet}</span>}
      </div>

      {szurt.length === 0 ? (
        <p className="text-[13px] text-text-muted">
          {kontaktok.length === 0 ? "Még nincs felvéve megrendelői kontakt." : "Nincs találat."}
        </p>
      ) : (
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Név</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Ügyfél</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Email</th>
              <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Telefon</th>
              <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Anyagok</th>
              <th className="py-1.5 text-right font-medium text-text-secondary" />
            </tr>
          </thead>
          <tbody>
            {szurt.map((k) => (
              <tr key={k.id} className="border-b border-border last:border-0">
                <td className="py-2 pr-4 text-text-primary">{k.full_name}</td>
                <td className="py-2 pr-4 text-text-secondary">{k.client_nev ?? "–"}</td>
                <td className="py-2 pr-4">
                  {k.email ? (
                    <a href={`mailto:${k.email}`} className="text-text-accent hover:underline">
                      {k.email}
                    </a>
                  ) : (
                    <span className="text-text-muted">–</span>
                  )}
                </td>
                <td className="py-2 pr-4 text-text-secondary">{k.phone ?? "–"}</td>
                {/* Hány anyagnál van beállítva, hogy neki is ki kell küldeni -
                    ebből látszik, kinek megy ténylegesen anyag. */}
                <td className="py-2 pr-4 text-right tabular-nums text-text-secondary">
                  {k.anyagok_szama > 0 ? k.anyagok_szama : "–"}
                </td>
                <td className="py-2 text-right whitespace-nowrap">
                  {canEdit && (
                    <button
                      type="button"
                      onClick={() => szerkeszt(k)}
                      title="Szerkesztés"
                      className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-primary"
                    >
                      <Pencil size={13} />
                    </button>
                  )}
                  {canDelete && (
                    <button
                      type="button"
                      onClick={() => torol(k)}
                      disabled={busy}
                      title="Törlés"
                      className="ml-1 rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {canCreate && (
        <button type="button" onClick={ujat} className="btn btn-primary mt-4">
          <Plus size={13} /> Kontakt felvétele
        </button>
      )}

      {urlap && (
        <ModalReteg onClose={busy ? undefined : () => setUrlap(null)}>
          <div
            className="my-auto w-full max-w-lg rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-[15px] font-medium text-text-primary">
              {szerkesztettId ? "Kontakt szerkesztése" : "Új kontakt"}
            </h3>
            <div className="grid grid-cols-1 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Név *</label>
                <input
                  value={urlap.full_name}
                  onChange={(e) => setUrlap({ ...urlap, full_name: e.target.value })}
                  className={inputClass}
                  autoFocus
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Ügyfél *</label>
                <select
                  value={urlap.client_id}
                  onChange={(e) => setUrlap({ ...urlap, client_id: e.target.value })}
                  disabled={!!szerkesztettId}
                  className={inputClass}
                >
                  {ugyfelek.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.nev}
                    </option>
                  ))}
                </select>
                {szerkesztettId && (
                  <p className="text-[11px] text-text-muted">
                    Meglévő kontaktot nem tesszük át másik ügyfélhez – vedd fel újként ott.
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Email</label>
                <input
                  type="email"
                  value={urlap.email}
                  onChange={(e) => setUrlap({ ...urlap, email: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Telefon</label>
                <input
                  value={urlap.phone}
                  onChange={(e) => setUrlap({ ...urlap, phone: e.target.value })}
                  className={inputClass}
                />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={() => setUrlap(null)}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={ment}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Mentés…" : "Mentés"}
              </button>
            </div>
          </div>
        </ModalReteg>
      )}
    </div>
  );
}
