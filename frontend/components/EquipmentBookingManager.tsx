"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { DeleteButton } from "@/components/DeleteButton";
import { SearchableIdPicker } from "@/components/SearchableIdPicker";

type EquipmentOption = { id: number; label: string; href: string; trackMode: string; kategoria: string | null };
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
  const [kivitelDatuma, setKivitelDatuma] = useState("");
  const [visszahozatalDatuma, setVisszahozatalDatuma] = useState("");
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
    const params = new URLSearchParams({ project_id: String(projectId) });
    if (kivitelDatuma) params.set("start_date", kivitelDatuma);
    if (visszahozatalDatuma || kivitelDatuma) params.set("end_date", visszahozatalDatuma || kivitelDatuma);
    authFetch(`/api/v1/equipment/${selected}/availability?${params.toString()}`)
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
  }, [selected, projectId, kivitelDatuma, visszahozatalDatuma]);

  const maxQty =
    availability && availability.track_mode === "stock" && typeof availability.available === "number"
      ? availability.available
      : undefined;

  /** Egy eszköz hozzáadása AZONNAL, a listára kattintáskor (a felhasználó
   * kérése: ne kelljen külön "Hozzáadás" gomb, és a lista maradjon nyitva,
   * hogy sorban több eszközt is hozzá lehessen kattintani). A darabszám a
   * mellette lévő mezőből jön; ugyanarra az eszközre újra kattintva a backend
   * a meglévő sor darabszámát növeli (lásd routes/equipment.py
   * create_assignment), nem nyit duplikált sort. */
  async function handleAdd(equipmentId: number) {
    if (busy) return;
    const requestedQty = Number(qty) || 1;
    // Az elérhetőség-őr csak arra az eszközre tud szólni, amire már le van
    // kérdezve (az előző kattintás óta kiválasztott) - a backend szándékosan
    // nem blokkol, a hivatalos ellenőrzés a "Technika ready" gomb.
    if (String(equipmentId) === selected && typeof maxQty === "number" && requestedQty > maxQty) {
      alert(`Csak ${maxQty} db érhető el ebből az eszközből erre az időszakra.`);
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/assignments", {
        method: "POST",
        body: JSON.stringify({
          equipment_id: equipmentId,
          project_id: projectId,
          qty: requestedQty,
          kivitel_datuma: kivitelDatuma || null,
          visszahozatal_datuma: visszahozatalDatuma || kivitelDatuma || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      // A kiválasztás megmarad: az elérhetőség-sor a most hozzáadott
      // eszközről ad visszajelzést, miközben a lista nyitva marad.
      setSelected(String(equipmentId));
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
        <SearchableIdPicker
          value={selected ? Number(selected) : null}
          options={options.map((o) => ({
            id: o.id,
            label: o.label,
            sublabel: o.trackMode === "stock" ? "készlet" : null,
            group: o.kategoria,
          }))}
          // A kattintás AZONNAL hozzáad, és a lista nyitva marad - egymás
          // után több eszköz is kattintható. A sorok színét a kategória adja
          // (hang, kamera…), így egy kategória egy szín.
          colorByGroup
          keepOpenOnSelect
          onChange={(next) => {
            if (next !== null) void handleAdd(next);
          }}
          placeholder="Eszköz hozzáadása…"
          className="min-w-[14rem]"
        />
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
        <div className="flex items-center gap-1">
          <label className="text-[11px] text-text-muted">Mikortól</label>
          <input
            type="date"
            value={kivitelDatuma}
            onChange={(e) => setKivitelDatuma(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-1">
          <label className="text-[11px] text-text-muted">Meddig</label>
          <input
            type="date"
            value={visszahozatalDatuma}
            onChange={(e) => setVisszahozatalDatuma(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
        </div>
      </div>
      <p className="mt-1 text-[11px] text-text-muted">
        A listára kattintva az eszköz azonnal hozzáadódik, a lista pedig nyitva marad – ugyanarra az eszközre
        újra kattintva a darabszám nő. A &quot;Mikortól&quot; / &quot;Meddig&quot; mező üresen hagyva a projekt
        teljes forgatási időszakára foglal.
      </p>
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
