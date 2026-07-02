import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function KampanyokPage() {
  return (
    <PlaceholderPage
      title="Kampányok"
      description="Önálló marketing entitás, nem kötve a Project Code maghoz. A backend API (GET/POST /api/v1/campaigns) már működik, a lista/naptár UI a Fázis 1 munka része."
      entities={["Campaign"]}
    />
  );
}
