import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function MediaPortalPage() {
  return (
    <PlaceholderPage
      title="Média & Portál"
      description="Feltöltött anyagok, ügyfél-nézet és opcionális Barion fizetés. A backend API (GET/POST /api/v1/media, /api/v1/folders, /api/v1/portal, /api/v1/payments) már működik, a feltöltés/lejátszó UI a Fázis 1 munka része."
      entities={["Media", "Folder", "Portal", "Payment"]}
    />
  );
}
