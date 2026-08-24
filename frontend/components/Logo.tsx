/** A "HYPE OS" logó-jelvény - a Sidebar ÉS a MobileNav fejlécében is
 * ugyanez, hogy a fiók megnyitva is a szokott felületnek hasson. */
export function Logo() {
  return (
    <div className="flex items-center gap-3">
      {/* A logó-jel egy matt titánlapka: nem világít, nem színez - csak
          jelöli, hol a rendszer eleje. */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius)] border border-border-strong bg-surface-4 text-text-secondary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M12 2 3 7v10l9 5 9-5V7l-9-5Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
            // currentColor, nem fix fehér: világos nézetben a fehér kitöltés
            // eltűnne a világos lapkán (lásd globals.css data-theme="light").
            fill="currentColor"
            fillOpacity={0.08}
          />
          <path d="M3 7l9 5 9-5M12 12v10" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="min-w-0">
        <p className="text-[13px] font-semibold tracking-[-0.01em] text-text-primary">HYPE OS</p>
        <p className="mt-0.5 text-[11px] text-text-muted">HYPE Brain</p>
      </div>
    </div>
  );
}
