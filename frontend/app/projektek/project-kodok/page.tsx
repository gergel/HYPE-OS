import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function ProjectKodokPage() {
  return (
    <PlaceholderPage
      title="Project Code-ok"
      description="A pénzügyi mag: ügyfél, keret, önköltség-számítás. A backend API (GET/POST /api/v1/project-codes) már működik, a lista/részlet UI a Fázis 1 munka része."
      entities={["ProjectCode", "Contract", "Expense", "Revenue"]}
    />
  );
}
