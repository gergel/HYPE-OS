"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ModalReteg } from "@/components/ModalReteg";
import { SajatPapirFeltoltes } from "@/components/SajatPapirFeltoltes";
import { StatusBadge } from "@/components/StatusBadge";
import { useConfirm } from "@/components/ConfirmProvider";
import { useToast } from "@/components/ToastProvider";
import { authFetch } from "@/lib/authFetch";
import { datum } from "@/lib/utokovetes";
import type { KeretAlairasAllapot, KeretModositas } from "@/lib/api";

/** Mit várunk aláírva ennél a keretszerződésnél - DOKUMENTUMONKÉNT.
 *
 * A keretszerződés és minden módosítása külön papír, külön aláírással. Egyetlen
 * "aláírásra vár" jelölésből sosem derülne ki, hogy magát a szerződést várjuk-e
 * még, vagy a tavaly kiküldött módosítást - ezért soronként kiírjuk, MELYIKET
 * és MIKORIT.
 *
 * A sor kattintására nyílik a kezelő, ahol a hiányzó aláírt példány feltölthető,
 * és új módosító dokumentum vehető fel. */
export function KeretAlairasok({
  contractId,
  allapot,
  cegNeve,
  canEdit,
}: {
  contractId: number;
  allapot: KeretAlairasAllapot | undefined;
  cegNeve: string;
  canEdit: boolean;
}) {
  const [nyitva, setNyitva] = useState(false);
  const varunk = allapot?.varunk ?? [];

  return (
    <span className="flex flex-col items-end gap-1">
      {varunk.length === 0 ? (
        <StatusBadge
          label={allapot?.szerzodes_alairva ? "Minden aláírva" : "Nincs mit visszavárni"}
          tone={allapot?.szerzodes_alairva ? "success" : "neutral"}
        />
      ) : (
        <>
          <StatusBadge label={`${varunk.length} papírt visszavárunk`} tone="warning" />
          <span className="text-right text-[11px] text-text-muted">
            {varunk.map((v) => `${v.fajta}${v.keltezes ? ` (${datum(v.keltezes)})` : ""}`).join(" · ")}
          </span>
        </>
      )}
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className="text-[11.5px] text-text-accent hover:underline"
      >
        {allapot && allapot.modositas_db > 0
          ? `Aláírások és ${allapot.modositas_db} módosítás`
          : "Aláírások és módosítások"}
      </button>

      {nyitva && (
        <KeretAlairasModal
          contractId={contractId}
          cegNeve={cegNeve}
          allapot={allapot}
          canEdit={canEdit}
          onClose={() => setNyitva(false)}
        />
      )}
    </span>
  );
}

function ModositasJelzo({ m }: { m: KeretModositas }) {
  if (m.allapot === "Kész" || m.alairt_file_url) return <StatusBadge label="Aláírva" tone="success" />;
  return <StatusBadge label="Aláírásra vár" tone="warning" />;
}

function KeretAlairasModal({
  contractId,
  cegNeve,
  allapot,
  canEdit,
  onClose,
}: {
  contractId: number;
  cegNeve: string;
  allapot: KeretAlairasAllapot | undefined;
  canEdit: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const [modositasok, setModositasok] = useState<KeretModositas[] | null>(null);
  const [busy, setBusy] = useState(false);

  const betolt = useCallback(async () => {
    const res = await authFetch(`/api/v1/contracts/${contractId}/modositasok`);
    setModositasok(res.ok ? await res.json() : []);
  }, [contractId]);

  useEffect(() => {
    void betolt();
  }, [betolt]);

  async function feltolt(path: string, file: File, uzenet: string) {
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    try {
      const res = await authFetch(path, { method: "POST", body: fd });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen feltöltés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      toast(uzenet);
      await betolt();
      router.refresh();
    } catch (err) {
      toast(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function torol(m: KeretModositas) {
    if (!(await confirm("Biztosan törlöd ezt a módosító dokumentumot?"))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/contracts/${contractId}/modositasok/${m.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        toast(`Sikertelen törlés: ${reszlet?.detail ?? res.status}`);
        return;
      }
      await betolt();
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <ModalReteg onClose={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-4">
          <h3 className="text-[15px] font-medium text-text-primary">{cegNeve} – aláírások</h3>
          <p className="mt-0.5 text-[12.5px] text-text-muted">
            A keretszerződést és minden módosítását KÜLÖN várjuk vissza aláírva.
          </p>
        </div>

        {/* 1. Maga a keretszerződés. */}
        <div className="border-b border-border px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[13px] font-medium text-text-primary">Keretszerződés</span>
            {allapot?.szerzodes_alairva ? (
              <StatusBadge label="Aláírva megérkezett" tone="success" />
            ) : allapot?.szerzodes_kikuldve ? (
              <StatusBadge label="Aláírásra vár" tone="warning" />
            ) : (
              <StatusBadge label="Még nem ment ki" tone="neutral" />
            )}
          </div>
          {canEdit && !allapot?.szerzodes_alairva && (
            <div className="mt-2">
              <SajatPapirFeltoltes
                cimke="Aláírt keretszerződés feltöltése"
                feltoltesPath={`/api/v1/contracts/${contractId}/alairt-fajl`}
                disabled={busy}
                onKesz={() => {
                  toast("Az aláírt keretszerződés feltöltve.");
                  router.refresh();
                  onClose();
                }}
              />
            </div>
          )}
        </div>

        {/* 2. A módosító dokumentumok - mindegyik külön aláírással. */}
        <div className="px-5 py-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[13px] font-medium text-text-primary">
              Módosító dokumentumok ({modositasok?.length ?? 0})
            </span>
            {canEdit && (
              <SajatPapirFeltoltes
                cimke="Módosító dokumentum feltöltése"
                feltoltesPath={`/api/v1/contracts/${contractId}/modositasok/sajat-fajl`}
                disabled={busy}
                onKesz={() => {
                  toast("A módosítás felvéve - most már aláírásra vár.");
                  void betolt();
                  router.refresh();
                }}
              />
            )}
          </div>

          {modositasok === null ? (
            <p className="text-[12.5px] text-text-muted">Betöltés…</p>
          ) : modositasok.length === 0 ? (
            <p className="text-[12.5px] text-text-muted">
              Ehhez a keretszerződéshez még nincs módosító dokumentum.
            </p>
          ) : (
            <ul className="space-y-2">
              {modositasok.map((m) => (
                <li key={m.id} className="rounded-[var(--radius)] border border-border p-3 text-[12.5px]">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-text-primary">Módosítás – {datum(m.keltezes)}</span>
                    <ModositasJelzo m={m} />
                  </div>
                  {m.megjegyzes && <p className="mt-0.5 text-text-secondary">{m.megjegyzes}</p>}
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    {m.file_url && (
                      <a
                        href={m.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        Módosítás megnyitása
                      </a>
                    )}
                    {m.alairt_file_url && (
                      <a
                        href={m.alairt_file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        Aláírt példány
                      </a>
                    )}
                    {canEdit && !m.alairt_file_url && (
                      <label className="cursor-pointer text-text-secondary hover:underline">
                        + Aláírt példány feltöltése
                        <input
                          type="file"
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file)
                              void feltolt(
                                `/api/v1/contracts/${contractId}/modositasok/${m.id}/alairt-fajl`,
                                file,
                                "Az aláírt módosítás feltöltve.",
                              );
                            e.target.value = "";
                          }}
                        />
                      </label>
                    )}
                    {canEdit && (
                      <button
                        type="button"
                        onClick={() => torol(m)}
                        disabled={busy}
                        className="text-text-danger hover:underline disabled:opacity-50"
                      >
                        Törlés
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex justify-end border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Bezárás
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
