"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import type { Vallalkozas } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

/** Számlázó cégek: kik azok, akiket egy cég küld a forgatásra.
 *
 * Miért kell? Mert velük magukkal nincs szerződésünk, az őket küldő céggel
 * viszont igen - ilyenkor tőlük nem kell eseti szerződést kérni, a cég
 * keretszerződése fedi őket (lásd backend routes/vallalkozasok.py).
 *
 * A tagság JAVASLAT, nem szabály: hogy egy konkrét forgatáson kinek a munkáját
 * ki számlázza, azt a projekt stáblistáján lehet beállítani ("Ki számláz
 * kiért"). Ugyanaz az ember hol saját nevében, hol egy cég alatt számlázhat. */
/** Amit egy számlázó cégről KÖTELEZŐ megadni - ugyanaz a hat mező, amit a
 * backend is megkövetel (lásd routes/vallalkozasok.py KOTELEZO_CEG_MEZOK).
 * Mind rákerül a cég nevére szóló papírra. */
const UJ_CEG_MEZOK: { mezo: string; cimke: string; pelda: string; szeles?: boolean }[] = [
  { mezo: "nev", cimke: "Cég neve", pelda: "Média Kft." },
  { mezo: "kepviselo", cimke: "Képviselő", pelda: "Kiss Péter" },
  { mezo: "szekhely", cimke: "Székhely", pelda: "1011 Budapest, Fő utca 1.", szeles: true },
  { mezo: "adoszam", cimke: "Adószám", pelda: "12345678-2-41" },
  { mezo: "nyilvantartasi_szam", cimke: "Nyilvántartási szám", pelda: "01-09-123456" },
  { mezo: "megbizas_targya", cimke: "Megbízás tárgya", pelda: "Operatőri munka", szeles: true },
];

export function VallalkozasKezelo({
  vallalkozasok,
  emberek,
  canEdit,
  canCreate,
  canDelete,
}: {
  vallalkozasok: Vallalkozas[];
  emberek: { id: number; full_name: string }[];
  canEdit: boolean;
  canCreate: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [nyitottId, setNyitottId] = useState<number | null>(null);
  // MINDEN mező kötelező, ami a cég nevére szóló papírra rákerül: ha bármelyik
  // hiányzik, a kiküldött szerződésen/TIG-en üres hely marad, amit utólag csak
  // új papírral lehet javítani. Ezért a felvitelnél kérjük be, nem a kiküldés
  // pillanatában (a backend is ezt követeli, lásd KOTELEZO_CEG_MEZOK).
  const [ujCegAdat, setUjCegAdat] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function hivas(path: string, init: RequestInit): Promise<boolean> {
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

  async function ujCeg() {
    const hianyzik = UJ_CEG_MEZOK.filter((m) => !(ujCegAdat[m.mezo] ?? "").trim()).map((m) => m.cimke);
    if (hianyzik.length > 0) {
      setHiba(`Ezek a mezők kötelezőek: ${hianyzik.join(", ")}. Mind rákerül a cég nevére szóló papírra.`);
      return;
    }
    const ok = await hivas("/api/v1/vallalkozasok", {
      method: "POST",
      body: JSON.stringify(
        Object.fromEntries(UJ_CEG_MEZOK.map((m) => [m.mezo, (ujCegAdat[m.mezo] ?? "").trim()])),
      ),
    });
    if (ok) setUjCegAdat({});
  }

  async function tagFelvetel(vallalkozasId: number, employeeId: number) {
    await hivas(`/api/v1/vallalkozasok/${vallalkozasId}/tagok`, {
      method: "POST",
      body: JSON.stringify({ employee_id: employeeId }),
    });
  }

  async function tagTorles(vallalkozasId: number, employeeId: number, nev: string) {
    if (!(await confirm(`Leveszed ${nev}-t erről a céglistáról? A már elkészült papírokat ez nem érinti.`))) return;
    await hivas(`/api/v1/vallalkozasok/${vallalkozasId}/tagok/${employeeId}`, { method: "DELETE" });
  }

  async function aktivValtas(v: Vallalkozas) {
    await hivas(`/api/v1/vallalkozasok/${v.id}`, {
      method: "PATCH",
      body: JSON.stringify({ aktiv: !v.aktiv }),
    });
  }

  async function cegTorles(v: Vallalkozas) {
    if (!(await confirm(`Biztosan törlöd a(z) "${v.nev}" céget?`))) return;
    await hivas(`/api/v1/vallalkozasok/${v.id}`, { method: "DELETE" });
  }

  return (
    <div>
      <p className="mb-3 text-[12.5px] text-text-muted">
        Ha egy céggel van keretszerződésünk, az általa küldött emberektől nem kérünk külön eseti szerződést – elég
        beállítani a projekten, hogy a munkájukat a cég számlázza. Az itteni tagság csak javaslat: az igazságot mindig
        a projekt „Ki számláz kiért” beállítása hordozza, mert ugyanaz az ember más-más forgatáson más cég alatt (vagy
        saját nevében) is számlázhat.
      </p>
      {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}

      {canCreate && (
        <div className="mb-4 flex flex-wrap items-end gap-2 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
          <p className="w-full text-[12px] text-text-muted">
            Új cég felvétele – mindegyik mező kötelező, mert mind rákerül a cég nevére szóló szerződésre és TIG-re.
          </p>
          {UJ_CEG_MEZOK.map((m) => (
            <div key={m.mezo} className="flex flex-col gap-1">
              <label className="text-[11px] text-text-muted">{m.cimke}</label>
              <input
                value={ujCegAdat[m.mezo] ?? ""}
                onChange={(e) => setUjCegAdat((elozo) => ({ ...elozo, [m.mezo]: e.target.value }))}
                placeholder={m.pelda}
                disabled={busy}
                className={`${m.szeles ? "min-w-[280px]" : "min-w-[190px]"} rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none`}
              />
            </div>
          ))}
          <button
            type="button"
            onClick={ujCeg}
            disabled={busy}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            <Plus size={13} className="mr-1 inline" />
            Cég felvétele
          </button>
        </div>
      )}

      {vallalkozasok.length === 0 ? (
        <p className="text-[13px] text-text-secondary">Még nincs felvéve számlázó cég.</p>
      ) : (
        <div className="space-y-2">
          {vallalkozasok.map((v) => {
            const nyitva = nyitottId === v.id;
            const tagIdk = new Set(v.tagok.map((t) => t.employee_id));
            const felvehetok = emberek.filter((e) => !tagIdk.has(e.id));
            return (
              <div key={v.id} className="rounded-[var(--radius)] border border-border">
                <button
                  type="button"
                  onClick={() => setNyitottId(nyitva ? null : v.id)}
                  className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3 text-left hover:bg-surface-3"
                >
                  <span className="flex flex-wrap items-center gap-3">
                    <span className="text-[13.5px] text-text-primary">{v.nev}</span>
                    {v.adoszam && <span className="text-[12px] text-text-muted">{v.adoszam}</span>}
                    <span className="text-[12px] text-text-muted">
                      {v.tagok.length} {v.tagok.length === 1 ? "ember" : "ember"}
                    </span>
                  </span>
                  <span className="flex items-center gap-2">
                    {v.van_ervenyes_keretszerzodes ? (
                      <StatusBadge label="Élő keretszerződés" tone="success" />
                    ) : (
                      <StatusBadge label="Nincs élő keretszerződés" tone="warning" />
                    )}
                    {!v.aktiv && <StatusBadge label="Inaktív" tone="neutral" />}
                  </span>
                </button>

                {nyitva && (
                  <div className="border-t border-border px-4 py-3">
                    <div className="mb-3 flex flex-wrap gap-4 text-[12.5px] text-text-secondary">
                      {v.szekhely && <span>Székhely: {v.szekhely}</span>}
                      {v.kepviselo && <span>Képviselő: {v.kepviselo}</span>}
                      {v.email && <span>E-mail: {v.email}</span>}
                      {v.keretszerzodes_id && (
                        <a href={`/szerzodesek/${v.keretszerzodes_id}`} className="text-text-accent hover:underline">
                          Keretszerződés megnyitása →
                        </a>
                      )}
                    </div>

                    <p className="mb-2 text-[12px] font-medium uppercase tracking-wide text-text-muted">
                      Kik tartoznak ide
                    </p>
                    {v.tagok.length === 0 ? (
                      <p className="mb-2 text-[13px] text-text-secondary">Még nincs hozzárendelt ember.</p>
                    ) : (
                      <ul className="mb-2 space-y-1">
                        {v.tagok.map((t) => (
                          <li key={t.employee_id} className="flex items-center justify-between gap-3 text-[13px]">
                            <a href={`/csapat/${t.employee_id}`} className="text-text-accent hover:underline">
                              {t.full_name}
                            </a>
                            {canEdit && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => tagTorles(v.id, t.employee_id, t.full_name)}
                                title="Levétel a céglistáról"
                                className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}

                    {canEdit && (
                      <KeresosSelect
                        value={null}
                        disabled={busy}
                        options={felvehetok.map((e) => ({ value: String(e.id), label: e.full_name }))}
                        onChange={(ertek) => tagFelvetel(v.id, Number(ertek))}
                        placeholder="+ Ember hozzáadása…"
                        className="min-w-[240px]"
                      />
                    )}

                    <div className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3">
                      {canEdit && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => aktivValtas(v)}
                          className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                        >
                          {v.aktiv ? "Inaktívra állítás" : "Újra aktívvá tétel"}
                        </button>
                      )}
                      {/* Törölni csak azt lehet, amire semmilyen papír nem
                          hivatkozik - egyébként az `aktiv` kapcsoló való rá
                          (lásd backend delete_vallalkozas). */}
                      {canDelete && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => cegTorles(v)}
                          className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                        >
                          Törlés
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
