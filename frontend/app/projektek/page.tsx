import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function ProjektekPage() {
  return (
    <PlaceholderPage
      title="Projektek"
      description="Konkrét forgatások egy Project Code-on belül. A backend API (GET/POST /api/v1/projects) már működik, a lista/kártya UI a Fázis 1 munka része."
      entities={["Project", "Assignment (crew)", "Assignment (equipment)"]}
    />
  );
}
