"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, Paperclip, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { ModalReteg } from "@/components/ModalReteg";
import { UjAlvallalkozoDialog, type UjAlvallalkozoElotoltes } from "@/components/UjAlvallalkozoDialog";
import { authFetch } from "@/lib/authFetch";
import type { DocumentAttachment } from "@/lib/api";

/** Egy máshol feltöltött, de ehhez a kiadáshoz tartozó számla (lásd backend
 * routes/finance.kiadas_atvezetett_szamlak). */
type AtvezetettSzamla = {
  filename: string;
  url: string;
  forras: string;
  forras_link: string | null;
};

function meret(bajt: number | null | undefined): string {
  if (!bajt) return "";
  if (bajt < 1024 * 1024) return ` · ${Math.round(bajt / 1024)} kB`;
  return ` · ${(bajt / 1024 / 1024).toFixed(1)} MB`;
}

/** Egy Kiadás számlái (a felhasználó kérése): ide közvetlenül fel lehet
 * tölteni a számlát, és ha a kiadás egy ÁTVEZETETT tétel (TIG-kifizetés,
 * autó-költés, KP forgalom), a forrásnál feltöltött számlák is itt látszanak -
 * nem kell újra feltölteni, és nem tűnik hiányzónak, ami megvan.
 *
 * SAJÁT állapotból dolgozik (nem a szerver-komponens props-ából), mert a
 * Kiadások listáján egy felugróban is él - minden művelet után újratölti a
 * két listát. */
export function KiadasSzamlak({
  expenseId,
  canEdit,
  canDelete,
}: {
  expenseId: number;
  canEdit: boolean;
  canDelete: boolean;
}) {
  const confirm = useConfirm();
  const router = useRouter();
  const [sajat, setSajat] = useState<DocumentAttachment[] | null>(null);
  const [atvezetett, setAtvezetett] = useState<AtvezetettSzamla[]>([]);
  const [hiba, setHiba] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  // A feltöltött számla KIOLVASÁSA (a felhasználó kérése): az AI a számlából
  // kitölti a kiadás ÜRES mezőit - a már kitöltötteket nem bántja. Az
  // eredményről itt szólunk; ha a partner nincs a rendszerben, az
  // alvJavaslat-ból nyitható az előtöltött "Új alvállalkozó" ablak.
  const [kiolvasasUzenet, setKiolvasasUzenet] = useState<string | null>(null);
  const [alvJavaslat, setAlvJavaslat] = useState<(UjAlvallalkozoElotoltes & { full_name?: string }) | null>(null);
  const [alvAblak, setAlvAblak] = useState(false);

  const betolt = useCallback(async () => {
    try {
      const [sajatRes, atvezRes] = await Promise.all([
        authFetch(`/api/v1/csatolmanyok/expense/${expenseId}`),
        authFetch(`/api/v1/finance/kiadas/${expenseId}/atvezetett-szamlak`),
      ]);
      if (!sajatRes.ok || !atvezRes.ok) {
        setHiba(`Nem sikerült betölteni a számlákat (HTTP ${sajatRes.ok ? atvezRes.status : sajatRes.status}).`);
        return;
      }
      setSajat(((await sajatRes.json()) as DocumentAttachment[]).filter((a) => a.kategoria === "szamla"));
      setAtvezetett((await atvezRes.json()) as AtvezetettSzamla[]);
      setHiba(null);
    } catch (err) {
      setHiba(`Nem sikerült betölteni a számlákat: ${err}`);
    }
  }, [expenseId]);

  useEffect(() => {
    // Adatbetöltés, nem szinkron setState: az állapot csak a hálózati válasz
    // megérkezésekor íródik - a szabály fals pozitívja.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void betolt();
  }, [betolt]);

  /** Az employee_id mellé a besorolást is külsősre állítjuk, ha még üres -
   * ugyanaz a szabály, mint a kiadás-űrlap autoSet-je (szerződés/TIG csak a
   * külsős besorolású kiadás emberéről jár). */
  async function alvallalkozoBeallitasa(employeeId: number) {
    const exp = await authFetch(`/api/v1/expenses/${expenseId}`)
      .then((r) => (r.ok ? (r.json() as Promise<Record<string, unknown>>) : null))
      .catch(() => null);
    const patch: Record<string, unknown> = { employee_id: employeeId };
    if (!exp?.tipus) patch.tipus = "kulsos";
    await authFetch(`/api/v1/expenses/${expenseId}`, { method: "PATCH", body: JSON.stringify(patch) });
    router.refresh();
  }

  /** A most feltöltött számla kiolvastatása (a felhasználó kérése): az AI-tól
   * kapott értékekkel a kiadás ÜRES mezőit töltjük ki (PATCH) - amit kézzel
   * már beírtak, azt nem írjuk felül. */
  async function kiolvasEsKitolt(file: File) {
    setKiolvasasUzenet("Számla kiolvasása…");
    setAlvJavaslat(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch("/api/v1/expenses/kiolvasas", { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setKiolvasasUzenet(`A számla kiolvasása nem sikerült: ${detail?.detail ?? res.status}`);
        return;
      }
      const adatok = (await res.json()) as Record<string, unknown> & {
        alvallalkozo?: { id: number; full_name: string } | null;
        alvallalkozo_adatok?: (UjAlvallalkozoElotoltes & { full_name?: string }) | null;
      };
      const exp = await authFetch(`/api/v1/expenses/${expenseId}`)
        .then((r) => (r.ok ? (r.json() as Promise<Record<string, unknown>>) : null))
        .catch(() => null);
      if (!exp) {
        setKiolvasasUzenet("A számla kiolvasása kész, de a kiadás adatai nem érhetők el.");
        return;
      }
      const patch: Record<string, unknown> = {};
      for (const kulcs of [
        "megnevezes",
        "kiadas_leiras",
        "netto",
        "plusz_afa",
        "afa_szazalek",
        "penznem",
        "kiadas_datuma",
        "employee_id",
      ]) {
        const uj = adatok[kulcs];
        if (uj === null || uj === undefined || uj === "" || typeof uj === "object") continue;
        const regi = exp[kulcs];
        // Csak az ÜRES mezőt töltjük - a "HUF" pénznem-alapértéket is békén
        // hagyjuk, azt csak üres értéknél írnánk.
        if (regi === null || regi === undefined || regi === "") patch[kulcs] = uj;
      }
      if (patch.employee_id !== undefined && !exp.tipus) patch.tipus = "kulsos";
      if (Object.keys(patch).length > 0) {
        const mentes = await authFetch(`/api/v1/expenses/${expenseId}`, {
          method: "PATCH",
          body: JSON.stringify(patch),
        });
        if (!mentes.ok) {
          const detail = await mentes.json().catch(() => null);
          setKiolvasasUzenet(`A kiolvasott adatok mentése nem sikerült: ${detail?.detail ?? mentes.status}`);
          return;
        }
      }
      const alvNev = adatok.alvallalkozo?.full_name;
      if (!adatok.alvallalkozo && adatok.alvallalkozo_adatok && !exp.employee_id) {
        setAlvJavaslat(adatok.alvallalkozo_adatok);
      }
      setKiolvasasUzenet(
        Object.keys(patch).length > 0
          ? `Számla kiolvasva – ${Object.keys(patch).length} üres mező kitöltve${alvNev ? `, alvállalkozó: ${alvNev}` : ""}. Ellenőrizd az adatokat.`
          : "Számla kiolvasva – minden mező ki volt már töltve, nem írtunk felül semmit.",
      );
      router.refresh();
    } catch (err) {
      setKiolvasasUzenet(`A számla kiolvasása nem sikerült (hálózati hiba): ${err}`);
    }
  }

  async function feltolt(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;
    const hibak: string[] = [];
    let elsoSikeres: File | null = null;
    for (const file of files) {
      setUploading(file.name);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await authFetch(`/api/v1/csatolmanyok/expense/${expenseId}?kategoria=szamla`, {
          method: "POST",
          body: fd,
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          hibak.push(`${file.name}: ${detail?.detail ?? res.status}`);
        } else if (!elsoSikeres) {
          elsoSikeres = file;
        }
      } catch (err) {
        hibak.push(`${file.name}: ${err}`);
      }
    }
    setUploading(null);
    if (hibak.length > 0) alert(`Sikertelen feltöltés:\n${hibak.join("\n")}`);
    void betolt();
    // Az ELSŐ sikeresen feltöltött számlából az AI kitölti a kiadás üres
    // mezőit (a felhasználó kérése) - a háttérben, a lista már frissül.
    if (elsoSikeres && canEdit) void kiolvasEsKitolt(elsoSikeres);
  }

  async function torol(doc: DocumentAttachment) {
    if (!(await confirm(`Törlöd a(z) "${doc.filename}" számlát?`))) return;
    setDeletingId(doc.id);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${doc.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      void betolt();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setDeletingId(null);
    }
  }

  if (hiba) return <p className="text-[13px] text-text-danger">{hiba}</p>;
  if (sajat === null) return <p className="text-[13px] text-text-muted">Betöltés…</p>;

  return (
    <div className="space-y-3">
      {sajat.length === 0 && atvezetett.length === 0 && (
        <p className="text-[13px] text-text-muted">Ehhez a kiadáshoz még nincs számla feltöltve.</p>
      )}
      {sajat.length > 0 && (
        <ul className="space-y-1.5">
          {sajat.map((doc) => (
            <li key={doc.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
              <span className="flex min-w-0 items-center gap-1.5">
                <Paperclip size={13} className="shrink-0 text-text-muted" />
                <a href={doc.url} target="_blank" rel="noopener noreferrer" className="truncate text-text-accent hover:underline">
                  {doc.filename}
                </a>
                <span className="shrink-0 text-[12px] text-text-muted">Számla{meret(doc.meret_bajt)}</span>
              </span>
              {canDelete && (
                <button
                  type="button"
                  onClick={() => torol(doc)}
                  disabled={deletingId === doc.id}
                  title="Számla törlése"
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
        <label className="inline-block cursor-pointer rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
          {uploading ? `Feltöltés… (${uploading})` : "+ Számla feltöltése"}
          <input type="file" multiple className="hidden" disabled={!!uploading} onChange={feltolt} />
        </label>
      )}
      {/* A feltöltött számla AI-s kiolvasásának eredménye (a felhasználó
          kérése: a számlából minden adatot szedjen ki) - és ha a partner
          nincs a rendszerben, innen vehető fel előtöltve. */}
      {kiolvasasUzenet && <p className="text-[12.5px] text-text-accent">{kiolvasasUzenet}</p>}
      {alvJavaslat && (
        <button
          type="button"
          onClick={() => setAlvAblak(true)}
          className="rounded-[var(--radius)] border border-dashed border-border px-3 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-3"
        >
          + „{alvJavaslat.full_name || alvJavaslat.vallakozas_neve}” felvétele alvállalkozóként (adatai előtöltve)
        </button>
      )}
      {alvAblak && alvJavaslat && (
        <UjAlvallalkozoDialog
          kezdoNev={alvJavaslat.full_name || ""}
          kezdoAdatok={alvJavaslat}
          onMegse={() => setAlvAblak(false)}
          onKesz={(id, nev) => {
            setAlvAblak(false);
            setAlvJavaslat(null);
            setKiolvasasUzenet(`Alvállalkozó felvéve és a kiadáshoz kötve: ${nev}.`);
            void alvallalkozoBeallitasa(id);
          }}
        />
      )}

      {/* Az átvezetett tétel forrásánál feltöltött számlák - csak olvasásra:
          törölni ott lehet, ahol feltöltötték. */}
      {atvezetett.length > 0 && (
        <div className="border-t border-border pt-3">
          <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">
            Átvezetett számlák
          </p>
          <ul className="space-y-1.5">
            {atvezetett.map((sz, i) => (
              <li key={`${sz.url}-${i}`} className="flex flex-wrap items-center gap-1.5 text-[13px]">
                <Paperclip size={13} className="shrink-0 text-text-muted" />
                <a href={sz.url} target="_blank" rel="noopener noreferrer" className="truncate text-text-accent hover:underline">
                  {sz.filename}
                </a>
                {sz.forras_link ? (
                  <a
                    href={sz.forras_link}
                    className="flex items-center gap-1 text-[12px] text-text-muted hover:text-text-secondary hover:underline"
                  >
                    {sz.forras}
                    <ExternalLink size={11} />
                  </a>
                ) : (
                  <span className="text-[12px] text-text-muted">{sz.forras}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Gemkapocs-gomb a Kiadások lista soraiba - felugróban nyitja a számlákat,
 * hogy feltöltéshez ne kelljen a kiadás saját lapjára átmenni. */
export function KiadasSzamlaGomb({
  expenseId,
  canEdit,
  canDelete,
  darab = 0,
}: {
  expenseId: number;
  canEdit: boolean;
  canDelete: boolean;
  /** Hány számla-fájl van fent ehhez a tételhez (saját + átvezetett) - a
   * lista tölti be egyben, lásd lib/api.getKiadasSzamlaDarab. */
  darab?: number;
}) {
  const [nyitva, setNyitva] = useState(false);
  return (
    <span onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        title={darab > 0 ? `Számlák (${darab} fájl)` : "Számlák"}
        className="inline-flex items-center gap-0.5 rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-accent"
      >
        <Paperclip size={14} className={darab > 0 ? "text-text-accent" : undefined} />
        {darab > 0 && <span className="text-[11px] text-text-secondary">{darab}</span>}
      </button>
      {nyitva && (
        <ModalReteg onClose={() => setNyitva(false)}>
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-3 text-[14px] font-medium text-text-primary">Számlák</h3>
            <KiadasSzamlak expenseId={expenseId} canEdit={canEdit} canDelete={canDelete} />
          </div>
        </ModalReteg>
      )}
    </span>
  );
}
