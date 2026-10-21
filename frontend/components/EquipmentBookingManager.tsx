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
/** Egy már hozzáadott KÉSZLETES eszköz darabszáma, helyben átírhatóan (a
 * felhasználó kérése) - Enter vagy elkattintás ment, Escape visszaáll. */
function SorDarabszam({ booking }: { booking: BookingRow }) {
  const router = useRouter();
  const [ertek, setErtek] = useState(String(booking.qty));
  const [busy, setBusy] = useState(false);

  async function ment() {
    const darab = Number(ertek);
    if (!Number.isFinite(darab) || darab < 1 || darab === booking.qty) {
      setErtek(String(booking.qty));
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/assignments/${booking.id}`, {
        method: "PATCH",
        body: JSON.stringify({ qty: darab }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        setErtek(String(booking.qty));
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
      setErtek(String(booking.qty));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-1">
      <input
        type="number"
        min={1}
        value={ertek}
        disabled={busy}
        onChange={(e) => setErtek(e.target.value)}
        onBlur={ment}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") setErtek(String(booking.qty));
        }}
        className="w-16 rounded-[var(--radius)] border border-border bg-surface-2 px-1.5 py-0.5 text-right text-[13px] text-text-primary focus:outline-none disabled:opacity-50"
        aria-label="Darabszám átírása"
      />
      <span>db</span>
    </span>
  );
}

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
  //: A készletes eszközre kattintáskor felugró darabszám-kérdés célpontja.
  const [darabKerdes, setDarabKerdes] = useState<{ id: number; label: string } | null>(null);
  const [darabErtek, setDarabErtek] = useState("1");
  const [kivitelDatuma, setKivitelDatuma] = useState("");
  const [visszahozatalDatuma, setVisszahozatalDatuma] = useState("");
  const [busy, setBusy] = useState(false);
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);

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
  async function handleAdd(equipmentId: number, requestedQty: number) {
    if (busy) return;
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
                  {/* Készletes eszköznél a darabszám helyben átírható (a
                      felhasználó kérése); az egyedi eszköz mindig 1 db. */}
                  {b.trackMode === "stock" ? <SorDarabszam booking={b} /> : `${b.qty} db (egyedi)`}
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
          // után több eszköz is kattintható. KÉSZLETES eszköznél előbb egy
          // felugró ablak kérdezi meg a darabszámot (a felhasználó kérése).
          // A sorok színét a kategória adja (hang, kamera…).
          colorByGroup
          keepOpenOnSelect
          onChange={(next) => {
            if (next === null) return;
            const opcio = options.find((o) => o.id === next);
            if (opcio?.trackMode === "stock") {
              setDarabErtek("1");
              setDarabKerdes({ id: next, label: opcio.label });
            } else {
              void handleAdd(next, 1);
            }
          }}
          placeholder="Eszköz hozzáadása…"
          className="min-w-[14rem]"
        />
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
        A listára kattintva az eszköz azonnal hozzáadódik, a lista pedig nyitva marad – készletes eszköznél
        előbb a darabszámot kérdezzük meg. A &quot;Mikortól&quot; / &quot;Meddig&quot; mező üresen hagyva a
        projekt teljes forgatási időszakára foglal.
      </p>
      {/* KÉSZLETES eszközre kattintva felugró darabszám-kérdés (a felhasználó
          kérése). A mousedown-stopPropagation azért kell, hogy a mögötte
          nyitva lévő eszköz-lista (AnchoredPanel) kívül-kattintás figyelője
          ne csukja be a listát, amíg itt gépelnek. */}
      {darabKerdes && (
        <div
          data-panel-tars=""
          className="fixed inset-0 z-[300] flex items-center justify-center bg-black/50 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setDarabKerdes(null);
          }}
        >
          <form
            className="w-72 rounded-[var(--radius-lg)] border border-border bg-surface-1 p-4 shadow-xl"
            onSubmit={(e) => {
              e.preventDefault();
              const darab = Math.max(1, Number(darabErtek) || 1);
              const cel = darabKerdes;
              setDarabKerdes(null);
              void handleAdd(cel.id, darab);
            }}
          >
            <p className="mb-2 text-[13px] text-text-primary">{darabKerdes.label}</p>
            <label className="mb-3 flex items-center gap-2 text-[13px] text-text-secondary">
              Hány darab kell?
              <input
                autoFocus
                type="number"
                min={1}
                value={darabErtek}
                onChange={(e) => setDarabErtek(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setDarabKerdes(null);
                }}
                className="w-20 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-right text-[13px] text-text-primary focus:outline-none"
              />
              db
            </label>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDarabKerdes(null)}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Mégse
              </button>
              <button
                type="submit"
                className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-2"
              >
                Hozzáadás
              </button>
            </div>
          </form>
        </div>
      )}
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
