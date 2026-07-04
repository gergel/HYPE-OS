import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function NaptarPage() {
  return (
    <PlaceholderPage
      title="Naptár / Diszpó"
      description="Projekt-eseménynapló és diszpó (előzetes/teljes email-szál). A backend API (GET/POST /api/v1/callsheets) már működik, a naptár/diszpó UI a Fázis 3 munka része."
      entities={["Callsheet", "TimelineEvent"]}
    />
  );
}
