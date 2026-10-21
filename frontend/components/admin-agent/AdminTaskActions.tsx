"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type ProposalRef = { id: number; eszkoz: string };

const KORREKCIO_TIPUSOK: { ertek: string; cimke: string }[] = [
  { ertek: "tenyszeru_hiba", cimke: "Tárgyi hiba (rossz adat)" },
  { ertek: "stilus", cimke: "Stílus / megfogalmazás" },
  { ertek: "besorolando", cimke: "Bizonytalan (emberi besorolás)" },
  { ertek: "egyszeri_kivetel", cimke: "Egyszeri kivétel" },
  { ertek: "uj_uzleti_adat", cimke: "Új üzleti adat (nem hiba)" },
];

/** Azok a feladattípusok, amelyekhez Lara tervezetet tud készíteni. */
const TERVEZHETO = new Set(["tig", "szerzodes", "email", "diszpo"]);

/** Lara — feladat-műveletek (kliens): tervezet készítése, javítás /
 * magyarázat, újraelemzés, megszakítás. Elég egy összefoglaló magyarázat
 * (mit hova kellett volna tennie és miért) — az azonnal Lara tudásába kerül;
 * a mezőszintű javítás opcionális (→ `aa_corrections`, a háttér-tanuló
 * dolgozza fel). Egyik sem aktivál szabályt. */

export function AdminTaskActions({
  taskId,
  tipus,
  proposals,
  canEdit,
  allapot,
}: {
  taskId: number;
  tipus: string;
  proposals: ProposalRef[];
  canEdit: boolean;
  /** A feladat állapota - a diszpó-tervezet visszavonása csak végrehajtott feladatnál. */
  allapot?: string;
}) {
  const router = useRouter();
  const [nyitva, setNyitva] = useState(false);
  const [proposalId, setProposalId] = useState<string>(proposals[0] ? String(proposals[0].id) : "");
  const [korrTipus, setKorrTipus] = useState("tenyszeru_hiba");
  const [magyarazat, setMagyarazat] = useState("");
  const [mezok, setMezok] = useState<{ mezo: string; ertek: string }[]>([{ mezo: "", ertek: "" }]);
  const [hiba, setHiba] = useState<string | null>(null);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);
  // Diszpó-tervezetnél: mit készítsen Lara.
  const [kellBrief, setKellBrief] = useState(true);
  const [kellDiszpoSzoveg, setKellDiszpoSzoveg] = useState(true);
  const [kellTechnika, setKellTechnika] = useState(true);

  if (!canEdit) {
    return <p className="text-[12px] text-text-muted">Javításhoz / művelethez szerkesztési jogosultság szükséges.</p>;
  }

  function ertekParse(s: string): unknown {
    const t = s.trim();
    if (t === "") return null;
    if (/^-?\d+(\.\d+)?$/.test(t)) return Number(t);
    if (t === "true" || t === "false") return t === "true";
    return t;
  }

  async function rogzitJavitas() {
    setHiba(null);
    setUzenet(null);
    const javitott: Record<string, unknown> = {};
    for (const { mezo, ertek } of mezok) {
      if (mezo.trim()) javitott[mezo.trim()] = ertekParse(ertek);
    }
    const vanMezo = Object.keys(javitott).length > 0;
    if (!vanMezo && !magyarazat.trim()) {
      setHiba("Írd le röviden, mit hova kellett volna tennie és miért.");
      return;
    }
    setFolyamatban(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/corrections`, {
        method: "POST",
        body: JSON.stringify({
          proposal_id: proposalId ? Number(proposalId) : null,
          javitott,
          tipus: korrTipus,
          magyarazat: magyarazat.trim() || null,
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => ({}))) as { detail?: unknown };
        setHiba(typeof d.detail === "string" ? d.detail : "A javítás rögzítése nem sikerült.");
        return;
      }
      setUzenet(
        vanMezo
          ? "Javítás rögzítve — a háttér-tanuló ebből dolgozik (Tanulás és minőség oldal)."
          : "Köszönöm, megtanultam — a magyarázatod bekerült a tudásomba, a hasonló eseteknél ebből dolgozom.",
      );
      setMezok([{ mezo: "", ertek: "" }]);
      setMagyarazat("");
      setNyitva(false);
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  async function tervezet() {
    setHiba(null);
    setUzenet(null);
    setFolyamatban(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/tervezet`, {
        method: "POST",
        body: tipus === "diszpo" ? JSON.stringify({ brief: kellBrief, technika: kellTechnika, diszpo_szoveg: kellDiszpoSzoveg }) : undefined,
      });
      const d = (await res.json().catch(() => ({}))) as { detail?: string; modell?: string; allapot?: string };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A tervezet elkészítése nem sikerült.");
        return;
      }
      const modellSzoveg =
        d.modell === "kesz"
          ? "Lara a megtanult példák alapján kiegészítette."
          : d.modell === "beallitas_szukseges"
            ? "A modell nincs beállítva (GEMINI_API_KEY) — a rendszer ismert adataiból előtöltöttem."
            : d.modell === "hiba"
              ? "A modell most nem válaszolt — a rendszer ismert adataiból előtöltöttem."
              : "";
      setUzenet(
        `Tervezet elkészült${d.allapot === "draft" ? " (hiányos — a „Javaslat szerkesztése” gombbal pótold)" : ""}. ${modellSzoveg}`,
      );
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  async function diszpoVisszavonas() {
    if (!window.confirm("Visszavonod Lara diszpó-módosítását? A hozzárendelt eszközök lekerülnek a projektről, a korábbi brief és diszpó-szöveg visszaáll (ha azóta senki nem írta át).")) return;
    setHiba(null);
    setUzenet(null);
    setFolyamatban(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/diszpo/visszavonas`, { method: "POST" });
      const d = (await res.json().catch(() => ({}))) as {
        detail?: string;
        torolt_foglalas?: number;
        brief?: string;
      };
      if (!res.ok) {
        setHiba(typeof d.detail === "string" ? d.detail : "A visszavonás nem sikerült.");
        return;
      }
      setUzenet(
        `Visszavonva: ${d.torolt_foglalas ?? 0} eszköz lekerült a projektről` +
          (d.brief === "visszaallitva"
            ? ", a korábbi brief visszaállt."
            : d.brief === "megtartva_mert_azota_modosult"
              ? "; a briefet azóta módosították, ezért az marad."
              : "."),
      );
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  async function muvelet(ut: "analyze" | "cancel") {
    setHiba(null);
    setUzenet(null);
    setFolyamatban(true);
    try {
      const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/${ut}`, { method: "POST" });
      if (!res.ok) {
        setHiba(ut === "analyze" ? "Az újraelemzés nem sikerült." : "A megszakítás nem sikerült.");
        return;
      }
      setUzenet(ut === "analyze" ? "Újraelemzés kész." : "A feladat megszakítva.");
      router.refresh();
    } finally {
      setFolyamatban(false);
    }
  }

  return (
    <div>
      {hiba && <div className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</div>}
      {uzenet && (
        <div className="mb-3 rounded-[var(--radius)] bg-bg-success px-3 py-2 text-[13px] text-text-success">{uzenet}</div>
      )}

      {tipus === "diszpo" && (
        <div className="mb-2 flex flex-wrap items-center gap-4 text-[13px] text-text-secondary">
          <span>Lara készítse el:</span>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={kellDiszpoSzoveg} onChange={(e) => setKellDiszpoSzoveg(e.target.checked)} />
            diszpó szövegét (érkezés, dresscode…)
          </label>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={kellBrief} onChange={(e) => setKellBrief(e.target.checked)} />
            briefet
          </label>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={kellTechnika} onChange={(e) => setKellTechnika(e.target.checked)} />
            technikai listát (az eszközök hozzárendelésével)
          </label>
        </div>
      )}
      <div className="mb-3 flex flex-wrap gap-2">
        {tipus === "diszpo" && allapot === "completed" && (
          <button
            type="button"
            disabled={folyamatban}
            onClick={diszpoVisszavonas}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Visszavonás (eszközök, brief, diszpó-szöveg)
          </button>
        )}
        {TERVEZHETO.has(tipus) && (
          <button
            type="button"
            disabled={folyamatban}
            onClick={tervezet}
            className="rounded-[var(--radius)] bg-bg-success px-3 py-1.5 text-[13px] font-medium text-text-success disabled:opacity-50"
          >
            {folyamatban ? "Dolgozom…" : "Tervezet készítése (Lara)"}
          </button>
        )}
        <button
          type="button"
          onClick={() => setNyitva((v) => !v)}
          className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent"
        >
          {nyitva ? "Mégse" : "Javítás / magyarázat Larának"}
        </button>
        {tipus === "szamla" && (
          <button
            type="button"
            disabled={folyamatban}
            onClick={() => muvelet("analyze")}
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[13px] font-medium text-text-primary hover:bg-surface-4 disabled:opacity-50"
          >
            Újraelemzés
          </button>
        )}
        <button
          type="button"
          disabled={folyamatban}
          onClick={() => muvelet("cancel")}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[13px] font-medium text-text-secondary hover:bg-surface-4 disabled:opacity-50"
        >
          Megszakítás
        </button>
      </div>

      {nyitva && (
        <div className="rounded-[var(--radius)] border border-border bg-surface-3 p-4">
          <label className="mb-1 block text-[13px] font-medium text-text-primary" htmlFor={`magyarazat-${taskId}`}>
            Mit hova kellett volna tennie, és miért?
          </label>
          <p className="mb-2 text-[12px] text-text-muted">
            Elég egy rövid, összefoglaló magyarázat — mezőket nem kell kitöltened. A magyarázatod azonnal Lara
            tudásába kerül, és a hasonló eseteknél (ugyanennél a partnernél, ilyen típusú feladatnál) ebből dolgozik.
          </p>
          <textarea
            id={`magyarazat-${taskId}`}
            value={magyarazat}
            onChange={(e) => setMagyarazat(e.target.value)}
            placeholder="pl. „Ez nem működési költség: a DEMO26-P014 forgatás technikai bérlése, ezért annak a projektkódnak a kiadásai közé kellett volna tenni. Ennél a bérlőcégnél mindig a forgatás kódjára megy.”"
            rows={4}
            className="mb-3 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted"
          />

          <details className="mb-3 rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2">
            <summary className="cursor-pointer text-[12.5px] text-text-secondary">
              Mezőszintű javítás (opcionális, haladó)
            </summary>
            <p className="mb-2 mt-2 text-[12px] text-text-muted">
              Ha pontosan tudod, melyik mező helyes értéke mi volt, itt megadhatod. Ebből a háttér-tanuló dolgozik —
              egyetlen javításból nem lesz automatikus szabály.
            </p>
          <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {proposals.length > 0 && (
              <label className="flex flex-col gap-1 text-[12px] text-text-muted">
                Melyik javaslathoz
                <select
                  value={proposalId}
                  onChange={(e) => setProposalId(e.target.value)}
                  className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
                >
                  {proposals.map((p) => (
                    <option key={p.id} value={p.id}>
                      #{p.id} — {p.eszkoz}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="flex flex-col gap-1 text-[12px] text-text-muted">
              Javítás típusa
              <select
                value={korrTipus}
                onChange={(e) => setKorrTipus(e.target.value)}
                className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
              >
                {KORREKCIO_TIPUSOK.map((k) => (
                  <option key={k.ertek} value={k.ertek}>
                    {k.cimke}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mb-2 flex flex-col gap-2">
            {mezok.map((m, i) => (
              <div key={i} className="flex gap-2">
                <input
                  value={m.mezo}
                  onChange={(e) => setMezok((p) => p.map((x, j) => (j === i ? { ...x, mezo: e.target.value } : x)))}
                  placeholder="mezőnév (pl. cel_project_code_id)"
                  className="flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted"
                />
                <input
                  value={m.ertek}
                  onChange={(e) => setMezok((p) => p.map((x, j) => (j === i ? { ...x, ertek: e.target.value } : x)))}
                  placeholder="helyes érték"
                  className="flex-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted"
                />
              </div>
            ))}
            <button
              type="button"
              onClick={() => setMezok((p) => [...p, { mezo: "", ertek: "" }])}
              className="self-start text-[12px] text-text-accent hover:underline"
            >
              + további mező
            </button>
          </div>
          </details>

          <button
            type="button"
            disabled={folyamatban}
            onClick={rogzitJavitas}
            className="rounded-[var(--radius)] bg-bg-accent px-3.5 py-1.5 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            {folyamatban ? "Mentés…" : "Elküldöm Larának"}
          </button>
        </div>
      )}
    </div>
  );
}
