import { PlaceholderPage } from "@/components/PlaceholderPage";

export default function AiAssistantPage() {
  return (
    <PlaceholderPage
      title="AI Assistant"
      description="RAG-alapú asszisztens a végleges Postgres felett, tool-calling-gal. A hype_os_build_roadmap.md szerint ez Fázis 5 munka - a backend API-alak (/api/v1/ai-assistant/ask) már lefektetve."
      entities={["RAG pipeline", "tool calling"]}
    />
  );
}
