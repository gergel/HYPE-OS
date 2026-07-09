"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useParams } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const MAX_FILES = 10;

type Prefill = {
  project_nev: string | null;
  projektkod: string | null;
  forgatas_datuma: string | null;
  forgatas_datuma_vege: string | null;
};

function formatDate(value: string | null): string {
  if (!value) return "–";
  const d = new Date(value);
  return d.toLocaleDateString("hu-HU");
}

/** Publikus (bejelentkezés nélküli) utókövető kérdőív - a diszpó résztvevőinek
 * a forgatás vége után 12 órával kiküldött emailben van a linkje (lásd
 * backend/app/workers/dispo_tasks.py). A projekt neve/kódja/dátuma csak
 * megjelenítésre való (a linket a projekthez kötő token miatt már ismert),
 * nem kell manuálisan beírni. */
export default function KerdoivPage() {
  const params = useParams();
  const token = params.token as string;

  const [prefill, setPrefill] = useState<Prefill | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [erdemlegesTortent, setErdemlegesTortent] = useState("");
  const [technikaInfo, setTechnikaInfo] = useState("");
  const [egyeb, setEgyeb] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/public/utokovetes/${token}`)
      .then(async (res) => {
        if (!res.ok) {
          setLoadError("Ez a link érvénytelen vagy lejárt.");
          return;
        }
        setPrefill(await res.json());
      })
      .catch(() => setLoadError("Nem sikerült betölteni az űrlapot (hálózati hiba)."))
      .finally(() => setLoading(false));
  }, [token]);

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []);
    const combined = [...files, ...picked].slice(0, MAX_FILES);
    setFiles(combined);
    e.target.value = "";
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const fd = new FormData();
      fd.append("erdemleges_tortent", erdemlegesTortent);
      fd.append("technika_info", technikaInfo);
      fd.append("egyeb", egyeb);
      for (const file of files) fd.append("files", file);

      const res = await fetch(`${API_BASE}/api/v1/public/utokovetes/${token}`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setSubmitError(detail?.detail ?? `Sikertelen küldés (${res.status}).`);
        return;
      }
      setDone(true);
    } catch (err) {
      setSubmitError(`Sikertelen küldés (hálózati hiba): ${err}`);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <Shell>
        <p className="text-[14px] text-text-muted">Betöltés…</p>
      </Shell>
    );
  }

  if (loadError) {
    return (
      <Shell>
        <p className="text-[14px] text-text-danger">{loadError}</p>
      </Shell>
    );
  }

  if (done) {
    return (
      <Shell>
        <h1 className="mb-2 text-[20px] font-medium text-text-primary">Köszönjük a visszajelzést!</h1>
        <p className="text-[14px] text-text-muted">A válaszod rögzítettük.</p>
      </Shell>
    );
  }

  return (
    <Shell>
      <h1 className="mb-1 text-[20px] font-medium text-text-primary">Utókövető kérdőív</h1>
      <p className="mb-6 text-[13px] text-text-muted">
        {prefill?.project_nev ?? "Projekt"}
        {prefill?.projektkod ? ` (${prefill.projektkod})` : ""} · {formatDate(prefill?.forgatas_datuma ?? null)}
        {prefill?.forgatas_datuma_vege ? ` – ${formatDate(prefill.forgatas_datuma_vege)}` : ""}
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <Field label="Történt-e bármi érdemleges, amit megosztanál velünk a forgatással kapcsolatban?">
          <textarea
            value={erdemlegesTortent}
            onChange={(e) => setErdemlegesTortent(e.target.value)}
            disabled={submitting}
            rows={4}
            className={textareaClass}
          />
        </Field>

        <Field label="Van-e bármi olyan információ, amit megosztanál velünk a Nálad levő technikával kapcsolatban (nem jó, elromlott, jobbra cserélnéd, stb.)?">
          <textarea
            value={technikaInfo}
            onChange={(e) => setTechnikaInfo(e.target.value)}
            disabled={submitting}
            rows={4}
            className={textareaClass}
          />
        </Field>

        <Field label="Bármi egyéb, amit úgy gondolod, hogy itt hagynál, a diszpódat követően? :)">
          <textarea
            value={egyeb}
            onChange={(e) => setEgyeb(e.target.value)}
            disabled={submitting}
            rows={4}
            className={textareaClass}
          />
        </Field>

        <Field label="Forgatás projektkódja">
          <input value={prefill?.projektkod ?? "–"} disabled readOnly className={`${textareaClass} opacity-70`} />
        </Field>

        <Field label="Forgatás dátuma">
          <input
            value={
              formatDate(prefill?.forgatas_datuma ?? null) +
              (prefill?.forgatas_datuma_vege ? ` – ${formatDate(prefill.forgatas_datuma_vege)}` : "")
            }
            disabled
            readOnly
            className={`${textareaClass} opacity-70`}
          />
        </Field>

        <Field label={`Werk fotó, ha készült (legfeljebb ${MAX_FILES} fájl, fájlonként max. 100 MB)`}>
          <div className="space-y-2">
            {files.length > 0 && (
              <ul className="space-y-1">
                {files.map((f, i) => (
                  <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-2 text-[13px] text-text-secondary">
                    <span className="truncate">{f.name}</span>
                    <button
                      type="button"
                      onClick={() => removeFile(i)}
                      disabled={submitting}
                      className="shrink-0 rounded-[var(--radius)] border border-border px-2 py-0.5 text-[12px] hover:bg-surface-3"
                    >
                      Eltávolítás
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {files.length < MAX_FILES && (
              <label className="inline-block cursor-pointer rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
                + Fájl feltöltése
                <input type="file" multiple className="hidden" disabled={submitting} onChange={handleFileChange} />
              </label>
            )}
          </div>
        </Field>

        {submitError && <p className="text-[13px] text-text-danger">{submitError}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-[var(--radius)] border border-border bg-bg-accent px-4 py-2 text-[14px] text-text-accent hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Küldés…" : "Kérdőív beküldése"}
        </button>
      </form>
    </Shell>
  );
}

const textareaClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary focus:outline-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius)] border border-border bg-surface-2 p-4">
      <label className="mb-2 block text-[13px] font-medium text-text-primary">{label}</label>
      {children}
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background px-6 py-10">
      <div className="mx-auto max-w-xl">{children}</div>
    </div>
  );
}
