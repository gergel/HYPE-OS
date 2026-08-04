import { AiAssistantChat } from "@/components/AiAssistantChat";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";

export default function AiAssistantPage() {
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title="AI Assistant" className="flex h-[calc(100vh-160px)] flex-col">
          <AiAssistantChat />
        </Card>
      </div>
    </div>
  );
}
