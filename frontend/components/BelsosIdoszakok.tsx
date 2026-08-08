"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import { huDatum } from "@/lib/huDate";
import type { EmployeeBelsosIdoszakok } from "@/lib/api";

const JOGVISZONYOK = [
  {
    ertek: "megbizas",
    cimke: "Folyamatos megbízási szerződés",
    magyarazat: "Havonta számláz – kell tőle havi TIG, számla és kifizetés-jelölés.",
  },
  {
    ertek: "alkalmazott",
    cimke: "Bejelentett alkalmazott",
    magyarazat: "A bérét bérszámfejtés fizeti – nincs TIG és nincs számla, csak a fizetését kell beírni havonta.",
  },
];

/** EGY munkatárs belsős beállításai: milyen JOGVISZONYBAN dolgozik, és mettől
 * meddig volt belsős.
 *
 * Ettől függ, mely hónapokra vár a rendszer havi TIG-et: aki márciusban lépett
 * be, attól januárra nincs mit kérni; aki augusztusban elment, attól
 * szeptemberre sincs. Enélkül ezek a hónapok örökre "hiányzó TIG"-ként
 * állnának a Belsős TIG oldalon.
 *
 * Több időszak is felvehető – ha valaki kilépett, majd visszajött, a köztes
 * hónapok kimaradnak.
 *
 * Ha nincs egyetlen időszak sem, a rendszer a munkatárs első/utolsó
 * munkanapjára esik vissza, annak híján pedig minden hónapra vár TIG-et (ez
 * volt a korábbi viselkedés). */
export function BelsosIdoszakok({
  adat,
  canEdit,
}: {
  adat: EmployeeBelsosIdoszakok;
  canEdit: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitva, setNyitva] = useState(false);
  const [jogviszony, setJogviszony] = useState(adat.jogviszony);
  const [kezdet, setKezdet] = useState("");
  const [veg, setVeg] = useState("");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function hivas(path: string, init: RequestInit) {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(path, init);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen művelet (HTTP ${res.status})`);
        return false;
      }
      router.refresh();
      return true;
    } catch (err) {
      setHiba(`Sikertelen művelet (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function felvesz() {
    if (!kezdet && !veg) {
      setHiba("Adj meg legalább egy dátumot. Üres kezdet = a kezdetektől, üres vég = azóta is itt van.");
      return;
    }
    const ok = await hivas(`/api/v1/belsos-idoszakok/${adat.employee_id}`, {
      method: "POST",
      body: JSON.stringify({ kezdet: kezdet || null, veg: veg || null }),
    });
    if (ok) {
      setKezdet("");
      setVeg("");
      setNyitva(false);
    }
  }

  async function torol(idoszakId: number) {
    if (!(await confirm("Törlöd ezt a belsős időszakot?"))) return;
    await hivas(`/api/v1/belsos-idoszakok/idoszak/${idoszakId}`, { method: "DELETE" });
  }

  // Ha nincs felvett időszak, a munkanapok döntenek - ezt ki is írjuk, hogy
  // látszódjon, mi alapján számol a rendszer.
  const munkanapSzoveg =
    adat.elso_munkanap || adat.utolso_munkanap
      ? `${adat.elso_munkanap ? huDatum(adat.elso_munkanap) : "a kezdetektől"} – ${
          adat.utolso_munkanap ? huDatum(adat.utolso_munkanap) : "azóta is"
        }`
      : null;

  async function jogviszonyValtas(ertek: string) {
    // Optimistán váltunk, hogy a rádiógomb azonnal reagáljon; hiba esetén
    // visszaáll (a router.refresh() úgyis a szerver állapotát hozza).
    const elozo = jogviszony;
    setJogviszony(ertek);
    const ok = await hivas(`/api/v1/belsos-idoszakok/${adat.employee_id}/jogviszony`, {
      method: "PUT",
      body: JSON.stringify({ jogviszony: ertek }),
    });
    if (!ok) setJogviszony(elozo);
  }

  const alkalmazott = jogviszony === "alkalmazott";

  return (
    <div>
      {/* Ez dönti el, kell-e egyáltalán havi TIG - ezért van legelöl. */}
      <div className="mb-4">
        <p className="mb-2 text-[12.5px] text-text-muted">Milyen formában dolgozik nálunk?</p>
        <div className="flex flex-col gap-1.5">
          {JOGVISZONYOK.map((j) => (
            <label
              key={j.ertek}
              className={`flex cursor-pointer items-start gap-2 rounded-[var(--radius)] border px-2.5 py-2 text-[13px] ${
                jogviszony === j.ertek ? "border-text-accent bg-bg-accent" : "border-border hover:bg-surface-3"
              } ${canEdit ? "" : "cursor-default opacity-80"}`}
            >
              <input
                type="radio"
                name={`jogviszony-${adat.employee_id}`}
                className="mt-0.5"
                checked={jogviszony === j.ertek}
                disabled={busy || !canEdit}
                onChange={() => jogviszonyValtas(j.ertek)}
              />
              <span>
                <span className="text-text-primary">{j.cimke}</span>
                <span className="block text-[11.5px] text-text-muted">{j.magyarazat}</span>
              </span>
            </label>
          ))}
        </div>
      </div>

      <p className="mb-3 text-[12.5px] text-text-muted">
        {alkalmazott
          ? "Csak azokra a hónapokra várjuk el a fizetése beírását, amikor tényleg belsős volt."
          : "Csak azokra a hónapokra várunk tőle havi TIG-et, amikor tényleg belsős volt."} Több időszak is felvehető – ha kilépett, majd visszajött, a köztes hónapok
        kimaradnak. Üres kezdet = „a kezdetektől”, üres vég = „azóta is itt van”.
      </p>
      {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}

      {adat.idoszakok.length === 0 ? (
        <p className="mb-3 text-[13px] text-text-secondary">
          {munkanapSzoveg
            ? `Nincs külön időszak megadva – a munkanapjai alapján számolunk: ${munkanapSzoveg}.`
            : alkalmazott
              ? "Nincs megadva – minden hónapra várjuk a fizetése beírását."
              : "Nincs megadva – minden hónapra várunk tőle TIG-et."}
        </p>
      ) : (
        <ul className="mb-3 space-y-1">
          {adat.idoszakok.map((i) => (
            <li key={i.id} className="flex items-center gap-2 text-[13px]">
              <span className="text-text-primary">
                {i.kezdet ? huDatum(i.kezdet) : "a kezdetektől"} – {i.veg ? huDatum(i.veg) : "azóta is"}
              </span>
              {canEdit && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => torol(i.id)}
                  title="Időszak törlése"
                  className="rounded-[var(--radius)] p-0.5 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEdit &&
        (nyitva ? (
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-0.5">
              <label className="text-[11px] text-text-muted">Mettől</label>
              <input
                type="date"
                value={kezdet}
                onChange={(e) => setKezdet(e.target.value)}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-0.5">
              <label className="text-[11px] text-text-muted">Meddig</label>
              <input
                type="date"
                value={veg}
                onChange={(e) => setVeg(e.target.value)}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none"
              />
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={felvesz}
              className="rounded-[var(--radius)] border border-border bg-bg-accent px-2.5 py-1 text-[12.5px] text-text-accent hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Mentés…" : "Mentés"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setNyitva(false);
                setHiba(null);
              }}
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
            >
              Mégse
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => {
              setNyitva(true);
              setKezdet("");
              setVeg("");
              setHiba(null);
            }}
            className="text-[12.5px] text-text-accent hover:underline"
          >
            <Plus size={12} className="mr-0.5 inline" />
            Időszak hozzáadása
          </button>
        ))}
    </div>
  );
}
