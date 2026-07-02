import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function UgyfelekPage() {
  return (
    <PlaceholderPage
      title="Ügyfelek"
      description="Cégek és kapcsolattartók. A backend API (GET/POST /api/v1/clients, /api/v1/contacts) már működik, a lista/részlet UI a Fázis 1 munka része."
      entities={["Client", "Contact"]}
    />
  );
}
