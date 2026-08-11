import Link from "next/link";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { TopBar } from "@/components/TopBar";
import { formatDate, formatHuf, getKulsosTigek, type KulsosTig } from "@/lib/api";

/** Külsős teljesítési igazolások: MINDEN TIG egy listában, a KIHAGYOTTAKKAL
 * együtt.
 *
 * Az Eseti szerződések oldal párja a TIG oldalán, és ugyanazért kell: eddig
 * csak szétszórva lehetett rájuk látni - projektenként az Utókövetésen,
 * emberenként a munkatárs adatlapján -, tehát arra a kérdésre, hogy "hol tart
 * összességében a külsős TIG-ezés", nem volt hely, ahol válasz lett volna.
 *
 * A kihagyottak azért vannak benne, mert egy kihagyott TIG ugyanúgy elszámolás,
 * mint egy kiküldött, csak papír nélkül - és pont az a néhány tétel, amit
 * később a legvalószínűbben számon kérnek. Az indokuk is itt látszik.
 *
 * A belsős TIG-ek NEM tartoznak ide: azok haviak, nem projektenkéntiek, és
 * saját oldaluk van (lásd /belsos-tig). */
export default async function KulsosTigekPage() {
  const rows = await getKulsosTigek();

  const kikuldott = rows.filter((t) => t.allapot === "Kiküldve").length;
  const kihagyott = rows.filter((t) => t.allapot === "Kihagyva").length;
  const keszul = rows.length - kikuldott - kihagyott;
  const kifizetve = rows.filter((t) => t.szamla_kifizetve).length;
  const osszesNetto = rows.reduce((sum, t) => sum + (t.netto_osszeg ?? 0), 0);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Külsős teljesítési igazolások (${rows.length})`}>
          <p className="mb-3 text-[12.5px] text-text-muted">
            {kikuldott} kiküldve, {kihagyott} kihagyva, {keszul} készül. {kifizetve} számla ki van fizetve. Összesen{" "}
            {formatHuf(osszesNetto)} nettó. A kihagyottaknál az indok is itt látszik. A havi belsős TIG-ek a{" "}
            <Link href="/belsos-tig" className="text-text-accent hover:underline">
              Belsős TIG
            </Link>{" "}
            oldalon vannak.
          </p>
          <DataTable<KulsosTig>
            filterable
            rows={rows}
            emptyText="Még nincs külsős teljesítési igazolás."
            // A sor a projekt utókövetésére visz: ott lehet a TIG-et
            // szerkeszteni, újraküldeni vagy törölni.
            getHref={(t) => (t.project_id ? `/utokovetes/${t.project_id}` : "/utokovetes")}
            columns={[
              {
                // A TIG MÁSIK OLDALA: a számlázó fél, akinek a nevére szól -
                // ember vagy cég. Alatta, hogy kinek a munkáját igazolja, ha
                // az nem ugyanaz (más nevében is számlázhat).
                header: "Kinek a nevére",
                render: (t) => (
                  <span>
                    {t.vallalkozas_id ? (
                      <StopClickPropagation>
                        <a href="/penzugyek/vallalkozasok" className="text-text-accent hover:underline">
                          {t.vallalkozas_nev ?? `#${t.vallalkozas_id}`}
                        </a>
                      </StopClickPropagation>
                    ) : t.employee_id ? (
                      <StopClickPropagation>
                        <a href={`/csapat/${t.employee_id}`} className="text-text-accent hover:underline">
                          {t.employee_nev ?? `#${t.employee_id}`}
                        </a>
                      </StopClickPropagation>
                    ) : (
                      <span className="text-text-muted">Nincs megbízott</span>
                    )}
                    {t.lefedettek.length > 0 && t.lefedettek.join(", ") !== (t.employee_nev ?? "") && (
                      <span className="block text-[11px] text-text-muted">{t.lefedettek.join(", ")} munkájáért</span>
                    )}
                  </span>
                ),
                sortAccessor: (t) => t.vallalkozas_nev ?? t.employee_nev,
              },
              {
                header: "Projekt",
                render: (t) => (
                  <span>
                    {t.project_id ? (
                      <StopClickPropagation>
                        <a href={`/projektek/${t.project_id}`} className="text-text-accent hover:underline">
                          {t.projektkod ? `${t.projektkod} – ` : ""}
                          {t.project_nev ?? `#${t.project_id}`}
                        </a>
                      </StopClickPropagation>
                    ) : (
                      <span className="text-text-muted">Nincs projekt</span>
                    )}
                    {/* Egy TIG több forgatást is igazolhat egy papíron. */}
                    {t.projektek_szama > 1 && (
                      <span className="block text-[11px] text-text-muted">
                        + még {t.projektek_szama - 1} projekt ugyanezen a papíron
                      </span>
                    )}
                  </span>
                ),
                sortAccessor: (t) => `${t.projektkod ?? ""} ${t.project_nev ?? ""}`.trim(),
              },
              {
                header: "Forgatás",
                render: (t) => formatDate(t.forgatas_datuma),
                sortAccessor: (t) => t.forgatas_datuma,
              },
              {
                header: "Nettó",
                align: "right",
                render: (t) => (t.netto_osszeg === null ? "–" : formatHuf(t.netto_osszeg)),
                sortAccessor: (t) => t.netto_osszeg,
              },
              {
                header: "Teljesítés",
                render: (t) => t.teljesites_szoveg ?? "–",
                sortAccessor: (t) => t.teljesites_szoveg,
              },
              {
                // A kihagyás INDOKA a jelölés alatt: egy "Kihagyva" sor
                // magyarázat nélkül pont azt a kérdést hagyná nyitva, ami miatt
                // az ember ránéz a listára.
                header: "Állapot",
                render: (t) => (
                  <span>
                    {t.allapot === "Kihagyva" ? (
                      <StatusBadge label="Kihagyva" tone="neutral" />
                    ) : t.allapot === "Kiküldve" ? (
                      <StatusBadge label="Kiküldve" tone="success" />
                    ) : (
                      <StatusBadge label={t.allapot ?? "Készítés alatt"} tone="warning" />
                    )}
                    {t.kihagyas_oka && (
                      <span className="mt-1 block max-w-[18rem] text-[11px] text-text-muted">{t.kihagyas_oka}</span>
                    )}
                  </span>
                ),
                sortAccessor: (t) => t.allapot,
              },
              {
                header: "Számla",
                render: (t) =>
                  t.szamla_kifizetve ? (
                    <StatusBadge label="Kifizetve" tone="success" />
                  ) : t.szamla_db > 0 ? (
                    <StatusBadge label={`${t.szamla_db} db, nincs kifizetve`} tone="warning" />
                  ) : (
                    <span className="text-text-muted">Nincs számla</span>
                  ),
                sortAccessor: (t) => (t.szamla_kifizetve ? 2 : t.szamla_db > 0 ? 1 : 0),
              },
              {
                header: "Keltezés",
                align: "right",
                render: (t) => formatDate(t.keltezes),
                sortAccessor: (t) => t.keltezes,
              },
              {
                header: "TIG",
                align: "right",
                render: (t) =>
                  t.file_url ? (
                    <StopClickPropagation>
                      <a
                        href={t.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        Megnyitás
                      </a>
                    </StopClickPropagation>
                  ) : (
                    <span className="text-text-muted">Nincs fájl</span>
                  ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
