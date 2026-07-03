"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { DeleteButton } from "@/components/DeleteButton";

type EquipmentOption = { id: number; label: string; href: string; trackMode: string };
type BookingRow = { id: number; label: string; href: string; qty: number; trackMode: string };

/** A Leltár (egyedi eszköz, qty=1) és a Stock igények (darabszámos, qty=N) egységes
 * hozzárendelési felülete egy projekthez - az Assignment tábla adja mindkettőt.
 * A tényleges ütközés-ellenőrzés a "Technika ready" gombbal fut le, itt a
 * hozzáadás/eltávolítás szabad. */
export function EquipmentBookingManager({
  projectId,
  bookings,
  options,
}: {
  projectId: number;
  bookings: BookingRow[];
  options: EquipmentOption[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState("");
  const [qty, setQty] = useState("1");
  const [busy, setBusy] = useState(false);

  const selectedOption = options.find((o) => String(o.id) === selected);

  async function handleAdd() {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/assignments", {
        method: "POST",
        body: JSON.stringify({ equipment_id: Number(selected), project_id: projectId, qty: Number(qty) || 1 }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      setSelected("");
      setQty("1");
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {bookings.length === 0 ? (
        <p className="mb-3 text-[13px] text-text-muted">Nincs eszköz hozzárendelve ehhez a projekthez.</p>
      ) : (
        <table className="mb-3 w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 text-left font-medium text-text-secondary">Eszköz</th>
              <th className="py-1.5 text-right font-medium text-text-secondary">Mennyiség</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {bookings.map((b) => (
              <tr key={b.id} className="border-b border-border last:border-0">
                <td className="py-2 pr-4">
                  <a href={b.href} className="text-text-accent hover:underline">
                    {b.label}
                  </a>
                </td>
                <td className="py-2 text-right">
                  {b.qty} db{b.trackMode === "stock" ? "" : " (egyedi)"}
                </td>
                <td className="py-2 text-right">
                  <DeleteButton path={`/api/v1/assignments/${b.id}`} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="flex items-center gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
        >
          <option value="">Válassz eszközt...</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
              {o.trackMode === "stock" ? " (készlet)" : ""}
            </option>
          ))}
        </select>
        {selectedOption?.trackMode === "stock" && (
          <input
            type="number"
            min={1}
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="w-20 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
        )}
        <button
          type="button"
          disabled={!selected || busy}
          onClick={handleAdd}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          Hozzáadás
        </button>
      </div>
    </div>
  );
}
