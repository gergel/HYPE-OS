"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ModalReteg } from "@/components/ModalReteg";
import { authFetch } from "@/lib/authFetch";

/** A három pontozott szempont. A sorrend a vágó gondolatmenetét követi: előbb
 * azt, amit KAPOTT (nyersanyag), aztán ahogy fel volt véve (technika), végül
 * ahogy meg volt komponálva (kreatív). */
const SZEMPONTOK = [
  {
    kulcs: "nyersanyag_felhasznalhatosaga" as const,
    cimke: "Nyersanyag felhasználhatósága",
    leiras: "Mennyi használható anyag volt, elég fedés volt-e a vágáshoz.",
  },
  {
    kulcs: "technikai_helyesseg" as const,
    cimke: "Technikai helyesség",
    leiras: "Fókusz, expozíció, hang, beállítások.",
  },
  {
    kulcs: "kreativ_kepivilag" as const,
    cimke: "Kreativitás és képi világ",
    leiras: "Képkivágás, kompozíció, ötletesség.",
  },
];

type Pontok = Partial<Record<(typeof SZEMPONTOK)[number]["kulcs"], number>>;

/** "Visszajelzés" gomb az utómunka oldalán: felugró űrlapot nyit, ahol a vágó
 * 1-10-ig pontozza a három szempontot, és megjegyzést írhat.
 *
 * A küldés egy VÁGÓI VISSZAJELZÉS rekordot hoz létre (lásd backend
 * routes/vagoi_visszajelzesek.py) - onnan lehet később kiküldeni a forgatás
 * diszpó-levelére válaszként. */
export function FeedbackSendButton({ deliverableId }: { deliverableId: number }) {
  const router = useRouter();
  const [nyitva, setNyitva] = useState(false);
  const [pontok, setPontok] = useState<Pontok>({});
  const [megjegyzes, setMegjegyzes] = useState("");
  const [busy, setBusy] = useState(false);

  function bezar() {
    setNyitva(false);
    setPontok({});
    setMegjegyzes("");
  }

  async function kuld() {
    const vanPont = SZEMPONTOK.some((sz) => pontok[sz.kulcs] != null);
    if (!vanPont && !megjegyzes.trim()) {
      alert("Adj legalább egy pontszámot, vagy írj megjegyzést.");
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/visszajelzes`, {
        method: "POST",
        body: JSON.stringify({
          nyersanyag_felhasznalhatosaga: pontok.nyersanyag_felhasznalhatosaga ?? null,
          technikai_helyesseg: pontok.technikai_helyesseg ?? null,
          kreativ_kepivilag: pontok.kreativ_kepivilag ?? null,
          megjegyzes: megjegyzes.trim() || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen küldés: ${detail?.detail ?? res.status}`);
        return;
      }
      bezar();
      router.refresh();
    } catch (err) {
      alert(`Sikertelen küldés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent hover:opacity-90"
      >
        Visszajelzés
      </button>

      {nyitva && (
        <ModalReteg onClose={busy ? undefined : bezar}>
          <div
            className="my-auto w-full max-w-xl rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">Vágói visszajelzés</h3>
            <p className="mb-5 text-[12px] text-text-muted">
              Milyen volt a leforgatott anyag? 1 = használhatatlan, 10 = kifogástalan.
            </p>

            <div className="space-y-5">
              {SZEMPONTOK.map((sz) => (
                <div key={sz.kulcs}>
                  <div className="mb-1.5 flex items-baseline justify-between gap-3">
                    <span className="text-[13px] text-text-primary">{sz.cimke}</span>
                    <span className="text-[13px] tabular-nums text-text-secondary">
                      {pontok[sz.kulcs] != null ? `${pontok[sz.kulcs]} / 10` : "nincs pontozva"}
                    </span>
                  </div>
                  {/* Tíz gomb egymás mellett: egy kattintás az egész pontozás,
                      nem kell csúszkát célozni vagy számot begépelni. */}
                  <div className="flex flex-wrap gap-1">
                    {Array.from({ length: 10 }, (_, i) => i + 1).map((ertek) => {
                      const aktiv = pontok[sz.kulcs] === ertek;
                      return (
                        <button
                          key={ertek}
                          type="button"
                          aria-label={`${sz.cimke}: ${ertek}`}
                          onClick={() =>
                            setPontok((elozo) => ({ ...elozo, [sz.kulcs]: aktiv ? undefined : ertek }))
                          }
                          className={`h-8 w-8 rounded-[var(--radius)] border text-[12.5px] tabular-nums transition-colors ${
                            aktiv
                              ? "border-border-strong bg-bg-accent font-medium text-text-accent"
                              : "border-border text-text-secondary hover:bg-surface-3"
                          }`}
                        >
                          {ertek}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-1 text-[11px] text-text-muted">{sz.leiras}</p>
                </div>
              ))}

              <div className="flex flex-col gap-1">
                <label className="text-[13px] text-text-primary">Megjegyzés</label>
                <textarea
                  rows={5}
                  value={megjegyzes}
                  onChange={(e) => setMegjegyzes(e.target.value)}
                  placeholder="Egyéb meglátások – ez az a rész, ami a stábnak is kiküldhető."
                  className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
                />
                <p className="text-[11px] text-text-muted">
                  A forgatás stábjának később CSAK ez a szöveg és a kész anyag linkje küldhető ki – a
                  pontszámok belső mérőszámok.
                </p>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={bezar}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={kuld}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Küldés…" : "Küldés"}
              </button>
            </div>
          </div>
        </ModalReteg>
      )}
    </>
  );
}
