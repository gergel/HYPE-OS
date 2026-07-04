"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { DeleteButton } from "@/components/DeleteButton";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type EquipmentOption = { id: number; label: string; href: string; trackMode: string };
type BookingRow = { id: number; label: string; href: string; qty: number; trackMode: string };
type Availability = {
  track_mode: string;
  available: boolean | number | null;
  detail?: string | null;
  keret?: number;
  foglalt?: number;
};

/** A Leltár (egyedi eszköz, qty=1) és a Stock igények (darabszámos, qty=N) egységes
 * hozzárendelési felülete egy projekthez - az Assignment tábla adja mindkettőt.
 * A tényleges ütközés-ellenőrzés a "Technika ready" gombbal fut le, itt a
 * hozzáadás/eltávolítás szabad - de a stock eszközöknél élőben mutatjuk, hány
 * darab elérhető még a projekt forgatási napjaira, hogy ne adjanak hozzá túl sokat. */
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
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);

  const selectedOption = options.find((o) => String(o.id) === selected);

  useEffect(() => {
    if (!selected) {
      setAvailability(null);
      setAvailabilityError(null);
      return;
    }
    let cancelled = false;
    setLoadingAvailability(true);
    setAvailability(null);
    setAvailabilityError(null);
    fetch(`${API_BASE_URL}/api/v1/equipment/${selected}/availability?project_id=${projectId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setAvailability(data);
      })
      .catch((err) => {
        if (!cancelled) setAvailabilityError(`Nem sikerült lekérdezni az elérhetőséget (hálózati hiba): ${err}`);
      })
      .finally(() => {
        if (!cancelled) setLoadingAvailability(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected, projectId]);

  const maxQty =
    availability && availability.track_mode === "stock" && typeof availability.available === "number"
      ? availability.available
      : undefined;

  async function handleAdd() {
    if (!selected) return;
    const requestedQty = Number(qty) || 1;
    if (typeof maxQty === "number" && requestedQty > maxQty) {
      alert(`Csak ${maxQty} db érhető el ebből az eszközből erre az időszakra.`);
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/assignments", {
        method: "POST",
        body: JSON.stringify({ equipment_id: Number(selected), project_id: projectId, qty: requestedQty }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      setSelected("");
      setQty("1");
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
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
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setQty("1");
          }}
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
            max={maxQty}
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="w-20 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
        )}
        <button
          type="button"
          disabled={!selected || busy || maxQty === 0}
          onClick={handleAdd}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          Hozzáadás
        </button>
      </div>
      {selected && (
        <p className={`mt-1.5 text-[12px] ${availabilityError ? "text-text-danger" : "text-text-muted"}`}>
          {loadingAvailability && "Elérhetőség ellenőrzése…"}
          {!loadingAvailability && availabilityError}
          {!loadingAvailability && !availabilityError && availability?.track_mode === "stock" &&
            `Elérhető: ${availability.available} db (${availability.keret} db keretből, ${availability.foglalt} db foglalt máshol erre az időszakra)`}
          {!loadingAvailability && !availabilityError && availability?.track_mode === "asset" &&
            (availability.available ? "Szabad erre az időszakra." : `Foglalt máshol: ${availability.detail}`)}
          {!loadingAvailability && !availabilityError && availability && availability.available === null && availability.detail}
        </p>
      )}
    </div>
  );
}
