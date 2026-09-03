"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ModalReteg } from "@/components/ModalReteg";
import { DateRangePicker, type DateRangeValue } from "@/components/DateRangePicker";
import { authFetch } from "@/lib/authFetch";

/** A "Feldarabolás" gomb felugró ablakkal (a felhasználó kérése): itt
 * választható ki, MELYIK napot vagy dátum-tartományt válasszuk le a
 * forgatásból - ugyanazzal a dátum-választóval, mint a projekt "Forgatás
 * dátuma" mezője. A leválasztott nap új projektként jön létre ugyanahhoz a
 * Project Code-hoz - az eredeti forgatás hossza nem változik, csak bekerül
 * mellé egy plusz esemény (lásd backend
 * services/project_actions.create_feldarabolas). */
export function FeldarabolasGomb({
  projectId,
  javasoltKezdet,
  redirectPrefix,
}: {
  projectId: number;
  /** Az ablak kezdő javaslata - a forgatás záró napja utáni nap (a régi
   * alapértelmezés), a hívó számolja ki. */
  javasoltKezdet: string | null;
  redirectPrefix: string;
}) {
  const router = useRouter();
  const [nyitva, setNyitva] = useState(false);
  const [value, setValue] = useState<DateRangeValue>({
    start: javasoltKezdet ?? "",
    startTime: "",
    end: "",
    endTime: "",
  });
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function darabol() {
    if (busy) return;
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/projects/${projectId}/feldarabolas`, {
        method: "POST",
        body: JSON.stringify({
          datum: value.start || null,
          datum_vege: value.end || null,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setHiba(String(data?.detail ?? `Sikertelen művelet (HTTP ${res.status}).`));
        return;
      }
      setNyitva(false);
      if (data && typeof data.id !== "undefined") {
        router.push(`${redirectPrefix}${data.id}`);
      } else {
        router.refresh();
      }
    } catch (err) {
      setHiba(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setValue({ start: javasoltKezdet ?? "", startTime: "", end: "", endTime: "" });
          setHiba(null);
          setNyitva(true);
        }}
        className="btn btn-primary"
      >
        Feldarabolás
      </button>

      {nyitva && (
        <ModalReteg onClose={busy ? undefined : () => setNyitva(false)}>
          <div
            className="my-auto w-full max-w-md rounded-[var(--radius)] border border-border bg-surface-2 p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-[15px] font-medium text-text-primary">Feldarabolás</h3>
            <p className="mt-1 text-[12.5px] text-text-secondary">
              Melyik napot vagy dátum-tartományt válasszuk le? A leválasztott időszak új
              projektként jön létre ugyanahhoz a Project Code-hoz (név, stáb, projektkód
              átmásolva) - az eredeti forgatás hossza nem változik, csak bekerül mellé egy
              plusz esemény.
            </p>
            <div className="mt-4">
              <DateRangePicker value={value} onChange={setValue} readOnly={busy} />
            </div>
            {hiba && (
              <p className="mt-3 rounded-[var(--radius)] border border-text-danger/40 bg-surface-3 px-3 py-2 text-[13px] text-text-danger">
                {hiba}
              </p>
            )}
            <div className="mt-4 flex justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={() => setNyitva(false)}
                disabled={busy}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={() => void darabol()}
                disabled={busy || !value.start}
                className="btn btn-primary disabled:opacity-50"
              >
                {busy ? "Darabolás…" : "Feldarabolás"}
              </button>
            </div>
          </div>
        </ModalReteg>
      )}
    </>
  );
}
