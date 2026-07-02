import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function UtomunkaPage() {
  return (
    <PlaceholderPage
      title="Utómunka"
      description="Vágandó anyagok, ledolgozott idő és gombos visszajelzés. A backend API (GET/POST /api/v1/deliverables, /api/v1/timesheets, /api/v1/feedback) már működik, a lista/kanban UI a Fázis 1 munka része."
      entities={["Deliverable", "Timesheet", "Feedback"]}
    />
  );
}
