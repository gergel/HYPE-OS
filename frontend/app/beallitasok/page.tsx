import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function BeallitasokPage() {
  return (
    <PlaceholderPage
      title="Beállítások"
      description="Felhasználók, szerepkörök (admin / operatőr / vágó / ügyfél) és rendszerbeállítások - Fázis 1 munka."
      entities={["Employee.role", "SystemRole"]}
    />
  );
}
