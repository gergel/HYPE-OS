import type { StocktakeSummary } from "@/lib/api";

/** A leltározás összesítése: mi nem "Jó" állapotú, miből hiányzik, és miből
 * van TÖBB az elvártnál.
 *
 * A többlet ugyanúgy eltérés, mint a hiány: vagy a nyilvántartás volt rossz,
 * vagy egy másik tétel alá könyvelt darabok kerültek elő. Ha nem írjuk ki,
 * a készlet csendben elcsúszik.
 *
 * Egy komponens szolgálja ki a szerkesztő és az eredmény oldalt is - korábban
 * a kettő egymás mellett, kézzel másolva élt, és így tudott elcsúszni. */
export function LeltarOsszesites({ summary, ures }: { summary: StocktakeSummary; ures: string }) {
  const vanMit =
    summary.problemas_statuszok.length > 0 ||
    summary.hianyzo_keszletek.length > 0 ||
    summary.tobblet_keszletek.length > 0;

  if (!vanMit) return <p className="text-[13px] text-text-muted">{ures}</p>;

  return (
    <div className="space-y-4">
      {summary.problemas_statuszok.length > 0 && (
        <div>
          <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">
            Ami nem &quot;Jó&quot; állapotú
          </p>
          <div className="space-y-2">
            {summary.problemas_statuszok.map((g) => (
              <div key={g.status}>
                <p className="text-[13px] font-medium text-text-primary">{g.status}</p>
                <ul className="ml-3 space-y-0.5 text-[13px] text-text-secondary">
                  {g.items.map((i) => (
                    <li key={i.equipment_id}>
                      <a href={`/felszereles/${i.equipment_id}`} className="hover:underline">
                        {i.nev}
                      </a>
                      {i.megjegyzes ? (
                        <span className="text-text-muted"> – {i.megjegyzes}</span>
                      ) : i.magyarazat_kell ? (
                        <span className="text-text-danger"> – nincs megírva, miért</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {summary.hianyzo_keszletek.length > 0 && (
        <div>
          <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">Hiányzó készlet</p>
          <ul className="space-y-1 text-[13px] text-text-secondary">
            {summary.hianyzo_keszletek.map((m) => (
              <li key={m.equipment_id} className="flex items-center justify-between">
                <a href={`/felszereles/${m.equipment_id}`} className="hover:underline">
                  {m.nev}
                </a>
                <span>
                  {m.counted_qty} / {m.expected_qty} db <span className="text-text-danger">(hiány: {m.hiany})</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {summary.tobblet_keszletek.length > 0 && (
        <div>
          <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">
            Amiből több van, mint az elvárt
          </p>
          <ul className="space-y-1 text-[13px] text-text-secondary">
            {summary.tobblet_keszletek.map((t) => (
              <li key={t.equipment_id} className="flex items-center justify-between">
                <a href={`/felszereles/${t.equipment_id}`} className="hover:underline">
                  {t.nev}
                </a>
                <span>
                  {t.counted_qty} / {t.expected_qty} db{" "}
                  <span className="text-text-warning">(többlet: +{t.tobblet})</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
