"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AdminAgentSettings } from "@/lib/api";

/** Lara — BEÁLLÍTÁSOK (kliens).
 *
 * A biztonságos alapállás kapcsolói. A modul és a mellékhatások KÜLÖN
 * engedélyezendők (a modul bekapcsolása önmagában még nem enged külső hatást),
 * a vészleállítás pedig TELJESEN leállítja Larát minden szálon (a tudása és a
 * kapcsolók állása megmarad, és visszakapcsolható).
 * A tényleges kikényszerítés a szerver-oldali policy engine dolga — ez a
 * felület csak beállítja a kapcsolókat. */
export function AdminBeallitasok({
  kezdo,
  canManage,
  emberek = [],
}: {
  kezdo: AdminAgentSettings;
  canManage: boolean;
  /** A választható felelősök (aktív munkatársak). */
  emberek?: { id: number; nev: string }[];
}) {
  const router = useRouter();
  const [b, setB] = useState<AdminAgentSettings>(kezdo);
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);
  const [leallitasIndok, setLeallitasIndok] = useState("");
  const [kezdet, setKezdet] = useState(kezdo.tanulas_kezdete ?? "2026-09-01");
  const [kezdetUzenet, setKezdetUzenet] = useState<string | null>(null);

  const megfigyelesBe = Boolean((b.engedett_forrasok as Record<string, unknown> | null)?.megfigyeles);
  const levelezesBe = Boolean((b.engedett_forrasok as Record<string, unknown> | null)?.levelezes);
  const asszisztensBe = Boolean((b.engedett_forrasok as Record<string, unknown> | null)?.asszisztens);
  const rendszerBe = Boolean((b.engedett_forrasok as Record<string, unknown> | null)?.rendszer);
  const limitek = (b.limitek as Record<string, unknown> | null) ?? {};
  // A gyorsított tanulás kapcsolói alapból BEKAPCSOLTAK (hiányzó kulcs = be).
  const limitBe = (kulcs: string) => limitek[kulcs] !== false;
  const minEset = Number(limitek.auto_jovahagyas_min ?? 3) || 3;
  const limitMent = (valtozas: Record<string, unknown>) => mentSettings({ limitek: { ...limitek, ...valtozas } });

  async function mentSettings(valtozas: {
    module_enabled?: boolean;
    side_effects_enabled?: boolean;
    engedett_forrasok?: Record<string, unknown>;
    limitek?: Record<string, unknown>;
    tanulas_kezdete?: string;
  }) {
    if (!canManage) return;
    setHiba(null);
    setKezdetUzenet(null);
    setFolyamatban(true);
    try {
      const res = await authFetch("/api/v1/admin-agent/settings", {
        method: "PATCH",
        body: JSON.stringify(valtozas),
      });
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A módosítás nem sikerült."));
        return;
      }
      const uj = (await res.json()) as AdminAgentSettings & {
        korszak?: { felreteve: number; visszahozva: number; regi_jovahagyott: number } | null;
        atvezetett_feladat?: number;
      };
      setB((elozo) => ({ ...elozo, ...uj }));
      if (uj.atvezetett_feladat) {
        setKezdetUzenet(`${uj.atvezetett_feladat} nyitott Lara-feladat került a felelőshöz.`);
      }
      if (uj.korszak) {
        setKezdetUzenet(
          `Mentve. ${uj.korszak.felreteve} régi jelölt félretéve, ${uj.korszak.visszahozva} visszahozva; ${uj.korszak.regi_jovahagyott} jóváhagyott régi példát Lara kisebb súllyal használ.`,
        );
      }
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  async function veszleallitas(be: boolean) {
    if (!canManage) return;
    setHiba(null);
    setFolyamatban(true);
    try {
      const res = be
        ? await authFetch("/api/v1/admin-agent/pause", {
            method: "POST",
            body: JSON.stringify({ indok: leallitasIndok.trim() || null }),
          })
        : await authFetch("/api/v1/admin-agent/resume", { method: "POST" });
      if (!res.ok) {
        setHiba(await hibaSzoveg(res, "A művelet nem sikerült."));
        return;
      }
      const eredmeny = (await res.json()) as { kill_switch: boolean; indok?: string | null };
      setB((elozo) => ({
        ...elozo,
        kill_switch: eredmeny.kill_switch,
        kill_switch_indok: eredmeny.indok ?? null,
      }));
      if (!be) setLeallitasIndok("");
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {hiba && (
        <div className="rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>
      )}
      {!canManage && (
        <div className="rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[13px] text-text-secondary">
          Csak megtekintés — a kapcsolók módosításához külön jogosultság szükséges.
        </div>
      )}

      <div
        className={`rounded-[var(--radius)] border px-4 py-3.5 ${
          b.csak_felelosnek !== false && !b.felelos ? "border-transparent bg-bg-danger" : "border-border bg-surface-3"
        }`}
      >
        <p className="text-[13px] font-medium text-text-primary">Lara felelőse</p>
        <p className="mt-0.5 text-[12px] text-text-muted">
          Laránál mindenért ő felel: minden Lara-feladat hozzá tartozik, minden ellenőrzésre / jóváhagyásra váró
          javaslat, kérdés és a napi összesítő hozzá fut be értesítésként (és bekapcsolt telefonon push-ként).
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            value={b.felelos?.id ?? ""}
            disabled={!canManage || folyamatban || b.kill_switch}
            onChange={(e) => e.target.value && limitMent({ felelos_employee_id: Number(e.target.value) })}
            className="min-w-[220px] rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary disabled:opacity-50"
            aria-label="Lara felelőse"
          >
            {!b.felelos && <option value="">— válaszd ki —</option>}
            {emberek.map((e) => (
              <option key={e.id} value={e.id}>
                {e.nev}
              </option>
            ))}
          </select>
          {b.csak_felelosnek !== false && !b.felelos && (
            <span className="text-[12px] text-text-danger">
              Nincs kiválasztva — addig Lara senkinek nem küld semmit, és javaslatot sem lehet jóváhagyni.
            </span>
          )}
        </div>
        <div className="mt-3 flex flex-col gap-3">
          <Kapcsolo
            cim="Minden csak a felelőshöz"
            leiras="Bekapcsolva Lara MÁSNAK SEMMIT nem küld: minden értesítés csak a felelőshöz megy, Lara javaslatait csak ő hagyhatja jóvá vagy utasíthatja el, és kimenő levelet Lara csak az ő saját címére küldhet. Kikapcsolva a jogosultság szerinti régi működés érvényes."
            aktiv={b.csak_felelosnek !== false}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ csak_felelosnek: v })}
          />
          <Kapcsolo
            cim="Értesítés Lara javaslatairól"
            leiras="Ha Lara egy feladatnál javaslatot tett (ellenőrzésre vagy jóváhagyásra vár) vagy adatot kér, a felelős értesítést kap, benne a feladat linkjével."
            aktiv={limitBe("feladat_ertesites")}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ feladat_ertesites: v })}
          />
        </div>
      </div>

      <Kapcsolo
        cim="Tanulás és megfigyelés (L0)"
        leiras="Bekapcsolva Lara félóránként megnézi a projektkódokon és az utókövetésben történt szerződés-, TIG- és számla/kiadás-lépéseket, a megrendelői szerződéseket és TIG-eket, a projektkód-kommenteket, a bevételeket (ki mikor fizetett), az utalások felvezetését, a kiadott árajánlatokat és a véglegesen törölt rekordokat, és éjszakánként tanul a javításokból. Csak olvas és jelölteket készít — üzleti rekordot nem módosít, ezért a modul kikapcsolt állapotában is biztonságos."
        aktiv={megfigyelesBe}
        tiltva={!canManage || folyamatban || b.kill_switch}
        onValt={(v) =>
          mentSettings({
            engedett_forrasok: { ...((b.engedett_forrasok as Record<string, unknown>) ?? {}), megfigyeles: v },
          })
        }
      />

      <Kapcsolo
        cim="Levelezés olvasása — szamla@hypestab.hu"
        leiras="Bekapcsolva Lara félóránként végigolvassa a postafiók a tanulás kezdete óta érkezett és onnan küldött leveleit (szöveg, válaszaitok, csatolmányok), és szálanként tudás-jelöltet készít — ezek a Tudástárban jóváhagyás után kerülnek a tudásába. Csak olvas: nem jelöl olvasottnak, nem mozgat, nem válaszol."
        aktiv={levelezesBe}
        tiltva={!canManage || folyamatban || b.kill_switch}
        onValt={(v) =>
          mentSettings({
            engedett_forrasok: { ...((b.engedett_forrasok as Record<string, unknown>) ?? {}), levelezes: v },
          })
        }
      />

      <Kapcsolo
        cim="AI asszisztens figyelése"
        leiras="Bekapcsolva Lara félóránként megnézi, mit kérdeztek az AI asszisztenstől és mit csinált meg (a végrehajtott, a felhasználó által elutasított és a hibás műveleteket is), és minden lezárt kérésből tudás-jelöltet készít — ezek a Tudástárban jóváhagyás után kerülnek a tudásába. Csak olvas."
        aktiv={asszisztensBe}
        tiltva={!canManage || folyamatban || b.kill_switch}
        onValt={(v) =>
          mentSettings({
            engedett_forrasok: { ...((b.engedett_forrasok as Record<string, unknown>) ?? {}), asszisztens: v },
          })
        }
      />

      <Kapcsolo
        cim="Teljes rendszer figyelése (csak tanulás)"
        leiras="Bekapcsolva Lara óránként átnézi az EGÉSZ HYPE OS-t (diszpó, forgatások, utómunka, portál, anyagbekérés, eszközök, papírok, pénzügy…): modulonként rendszerismeretet és projektkódonként életutat tanul — pl. egy TIG-nél látja, hogy az utómunka leadva, a portál kiküldve. Csak olvas; személyes és titkos adatot (jelszó, token, bankszámla, e-mail, telefon, munkatársi adatlap) nem néz. Feladatot továbbra is KIZÁRÓLAG adminisztrációs területen végez (számla, TIG, szerződés, adminisztrációs e-mail) — más területhez nem nyúlhat."
        aktiv={rendszerBe}
        tiltva={!canManage || folyamatban || b.kill_switch}
        onValt={(v) =>
          mentSettings({
            engedett_forrasok: { ...((b.engedett_forrasok as Record<string, unknown>) ?? {}), rendszer: v },
          })
        }
      />

      <div className="rounded-[var(--radius)] border border-border px-4 py-3.5">
        <p className="text-[13px] font-medium text-text-primary">Gyorsított tanulás</p>
        <p className="mt-0.5 text-[12px] text-text-muted">
          Ezek gyorsítják, hogy az összegyűjtött tudásból használt tudás legyen. Mind csak Lara saját tudását és az
          értesítéseket érinti — üzleti rekordot nem módosít, és szabályt magától sosem élesít.
        </p>
        <div className="mt-3 flex flex-col gap-3">
          <Kapcsolo
            cim="Automatikus jóváhagyás, ha a valóság igazolta"
            leiras={`Ha ugyanannál a partnernél legalább ${minEset} eset egybehangzóan ugyanúgy alakult (és egyiket sem vetettétek el), Lara magától jóváhagyja ezeket a PÉLDÁKAT. A kommentek, árajánlatok és törlések mindig kézi jóváhagyásra várnak; a befolyt fizetés tény, az magától bekerül. Szabályból csak javaslat lesz.`}
            aktiv={limitBe("auto_jovahagyas")}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ auto_jovahagyas: v })}
          />
          <div className="flex flex-wrap items-center gap-2 pl-1 text-[12px] text-text-secondary">
            Ennyi egybehangzó eset kell hozzá:
            <select
              value={minEset}
              disabled={!canManage || folyamatban || b.kill_switch || !limitBe("auto_jovahagyas")}
              onChange={(e) => limitMent({ auto_jovahagyas_min: Number(e.target.value) })}
              className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12.5px] text-text-primary disabled:opacity-50"
            >
              {[2, 3, 4, 5, 7, 10].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <Kapcsolo
            cim="Jelentés szerinti keresés"
            leiras="A jóváhagyott tudást a jelentése alapján is megtalálja (pl. ugyanaz a cég más néven, vagy hasonló eset egy másik partnernél), nem csak ha a partner neve egyezik. A már beállított Gemini-kulcsot használja; hiba esetén a régi, név szerinti keresésre marad."
            aktiv={limitBe("szemantikus_kereses")}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ szemantikus_kereses: v })}
          />
          <Kapcsolo
            cim="Napi összesítő"
            leiras="Munkanapokon reggel értesítés (és bekapcsolt telefonon push) a felelősnek: hány tudás-jelölt vár, és melyek a legértékesebbek — ezek a Tudástárban „érték szerint” rendezve elöl állnak."
            aktiv={limitBe("napi_osszesito")}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ napi_osszesito: v })}
          />
          <Kapcsolo
            cim="Értesítés Lara kérdéseiről"
            leiras="Lara új kérdéseiről értesítés (és push) megy — „Minden csak a felelőshöz” módban a felelősnek, egyébként annak, aki az adott számlát rögzítette. Több új kérdésnél egy összefoglaló értesítés megy."
            aktiv={limitBe("kerdes_ertesites")}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ kerdes_ertesites: v })}
          />
          <Kapcsolo
            cim="Utánanézés kérdés előtt (az AI asszisztens tudásával)"
            leiras="Mielőtt kérdez, Lara maga is utánanéz a rendszerben — ugyanazokkal a csak-olvasó eszközökkel és tudással, amivel az AI asszisztens dolgozik, a felelős jogosultságával. Semmit nem módosít; amit talál, azt a kérdés mellett látod, és egy kattintással elfogadhatod. Kétóránként legfeljebb 3 kérdésnél (a Gemini-kulcsot használja)."
            aktiv={limitBe("nyomozas")}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ nyomozas: v })}
          />
          <Kapcsolo
            cim="Megoldási javaslat a feladatokhoz"
            leiras="A kérdésekből született javítási feladatokhoz (és a többi „egyéb” feladathoz) Lara konkrét megoldási lépéseket javasol: utánanéz az érintett rekordoknak az AI asszisztens csak-olvasó eszközeivel. Semmit nem módosít. Kétóránként legfeljebb 3 feladatnál, és a feladat oldalán kézzel bármikor."
            aktiv={limitBe("megoldas")}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ megoldas: v })}
          />
          <Kapcsolo
            cim="Gyorsított tanulás a Geminivel"
            leiras="Éjszakánként partner-profilt ír (ahol legalább 3 jóváhagyott eset van), szabályt javasol, és önreflexiót végez a saját hibáiból. Ugyanazt a Gemini-kapcsolatot használja, mint az AI asszisztens. Minden eredmény jelölt — a Tudástárban hagyod jóvá."
            aktiv={limitBe("gemini_tanulas")}
            tiltva={!canManage || folyamatban || b.kill_switch}
            onValt={(v) => limitMent({ gemini_tanulas: v })}
          />
        </div>
      </div>

      <div className="rounded-[var(--radius)] border border-border bg-surface-3 px-4 py-3.5">
        <p className="text-[13px] font-medium text-text-primary">Tanulás kezdete</p>
        <p className="mt-0.5 text-[12px] text-text-muted">
          Lara csak az ettől a naptól a HYPE OS-ben keletkezett munkából készít példa-jelöltet (a Notion-korszak
          és a Notionből hozott rekordok kimaradnak). A régebbi, már jóváhagyott példákat csak az újak után, kisebb
          súllyal használja; a régi, el nem bírált jelöltek félre lesznek téve (nem törlődnek).
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={kezdet}
            max={new Date().toISOString().slice(0, 10)}
            disabled={!canManage || folyamatban}
            onChange={(e) => setKezdet(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary disabled:opacity-50"
          />
          <button
            type="button"
            disabled={!canManage || folyamatban || b.kill_switch || !kezdet || kezdet === b.tanulas_kezdete}
            onClick={() => mentSettings({ tanulas_kezdete: kezdet })}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            Mentés
          </button>
        </div>
        {kezdetUzenet && <p className="mt-2 text-[12px] text-text-success">{kezdetUzenet}</p>}
      </div>

      <Kapcsolo
        cim="Modul engedélyezése"
        leiras="Bekapcsolva Lara elemez és javaslatokat készít. A mellékhatások (rekordírás, e-mail) ettől még külön engedély nélkül tiltottak maradnak."
        aktiv={b.module_enabled}
        tiltva={!canManage || folyamatban || b.kill_switch}
        onValt={(v) => mentSettings({ module_enabled: v })}
      />

      <Kapcsolo
        cim="Mellékhatások engedélyezése"
        leiras="A jóváhagyott műveletek tényleges végrehajtása (üzleti rekord írása, e-mail). Csak akkor van értelme, ha a modul is be van kapcsolva. Az R3 kockázatú lépések ekkor is tiltottak."
        aktiv={b.side_effects_enabled}
        tiltva={!canManage || folyamatban || b.kill_switch}
        onValt={(v) => mentSettings({ side_effects_enabled: v })}
      />

      <div
        className={`rounded-[var(--radius)] border px-4 py-3.5 ${
          b.kill_switch ? "border-transparent bg-bg-danger" : "border-border bg-surface-3"
        }`}
      >
        <p className={`text-[13px] font-medium ${b.kill_switch ? "text-text-danger" : "text-text-primary"}`}>
          {b.kill_switch ? "Lara le van állítva" : "Vészleállítás — Lara teljes leállítása"}
        </p>
        <p className={`mt-0.5 text-[12px] ${b.kill_switch ? "text-text-danger/80" : "text-text-muted"}`}>
          {b.kill_switch
            ? "Minden szál áll: ütemezett megfigyelés, tanulás, önellenőrzés, levelezés-olvasás és értékelés sem fut, és semmilyen elemzés, tervezet vagy végrehajtás nem indítható. A tudása (szabályok, példák, kérdések) és a kapcsolók állása megmaradt — visszakapcsolás után pontosan innen folytatja."
            : "Azonnal és teljesen leállítja Larát minden szálon: az ütemezett feladatok nem futnak, a futók a következő ellenőrzési ponton megállnak, és semmi nem indítható. A tudása NEM vész el, és bármikor visszakapcsolható. A már elindult, nem megszakítható külső műveleteket nem vonja vissza."}
        </p>
        {b.kill_switch ? (
          <div className="mt-3">
            {b.kill_switch_indok && (
              <p className="mb-2 text-[12px] text-text-danger/80">Indok: {b.kill_switch_indok}</p>
            )}
            <button
              type="button"
              disabled={!canManage || folyamatban}
              onClick={() => veszleallitas(false)}
              className="rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-4 disabled:opacity-50"
            >
              Lara visszakapcsolása
            </button>
          </div>
        ) : (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <input
              value={leallitasIndok}
              onChange={(e) => setLeallitasIndok(e.target.value)}
              placeholder="Indok (opcionális)"
              disabled={!canManage || folyamatban}
              className="min-w-[180px] flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted disabled:opacity-50"
            />
            <button
              type="button"
              disabled={!canManage || folyamatban}
              onClick={() => veszleallitas(true)}
              className="rounded-[var(--radius)] bg-bg-danger px-3 py-1.5 text-[13px] font-medium text-text-danger disabled:opacity-50"
            >
              Lara leállítása
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Kapcsolo({
  cim,
  leiras,
  aktiv,
  tiltva,
  onValt,
}: {
  cim: string;
  leiras: string;
  aktiv: boolean;
  tiltva: boolean;
  onValt: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-[var(--radius)] border border-border bg-surface-3 px-4 py-3.5">
      <div>
        <p className="text-[13px] font-medium text-text-primary">{cim}</p>
        <p className="mt-0.5 text-[12px] text-text-muted">{leiras}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={aktiv}
        disabled={tiltva}
        onClick={() => onValt(!aktiv)}
        className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
          aktiv ? "bg-bg-success" : "bg-surface-4"
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-text-primary transition-transform ${
            aktiv ? "left-0.5 translate-x-5" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}

async function hibaSzoveg(res: Response, alap: string): Promise<string> {
  try {
    const adat = (await res.json()) as { detail?: unknown };
    if (typeof adat.detail === "string") return adat.detail;
  } catch {
    // nem JSON
  }
  return alap;
}
