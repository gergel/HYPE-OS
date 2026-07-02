import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function CsapatPage() {
  return (
    <PlaceholderPage
      title="Csapat"
      description="Belsős, külsős, vágó, kreatív és stáb crew tagok, bérezési szabályokkal. A backend API (GET/POST /api/v1/crew, /api/v1/rates) már működik, a lista/részlet UI a Fázis 1 munka része."
      entities={["Employee", "Rate"]}
    />
  );
}
