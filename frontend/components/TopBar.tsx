const WEEKDAYS = ["vasárnap", "hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat"];
const MONTHS = [
  "január",
  "február",
  "március",
  "április",
  "május",
  "június",
  "július",
  "augusztus",
  "szeptember",
  "október",
  "november",
  "december",
];

function formatHuDate(date: Date): string {
  return `${date.getFullYear()}. ${MONTHS[date.getMonth()]} ${date.getDate()}., ${WEEKDAYS[date.getDay()]}`;
}

export function TopBar({ greetingName = "Gergő" }: { greetingName?: string }) {
  const today = formatHuDate(new Date());

  return (
    <div className="flex items-center justify-between border-b border-border px-6 py-4">
      <div>
        <p className="text-lg font-medium text-text-primary">Jó reggelt, {greetingName}</p>
        <p className="mt-0.5 text-[13px] text-text-secondary">{today}</p>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-bg-accent text-[13px] font-medium text-text-accent">
          GV
        </div>
      </div>
    </div>
  );
}
