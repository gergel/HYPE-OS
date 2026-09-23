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
const TERVEZHETO = new Set(["tig", "szerzodes", "email"]);

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
}: {
  taskId: number;
  tipus: string;
  proposals: ProposalRef[];
  canEdit: boolean;
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
      const res = await authFetch(`/api/v1/admin-agent/tasks/${taskId}/tervezet`, { method: "POST" });
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

      <div className="mb-3 flex flex-wrap gap-2">
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
