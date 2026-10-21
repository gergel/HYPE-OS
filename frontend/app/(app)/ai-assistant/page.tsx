import { AiAssistantChat } from "@/components/AiAssistantChat";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";

export default function AiAssistantPage() {
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      {/* A magasság 100dvh-ból számolódik (nem 100vh-ból): telefonon a
          böngésző el-eltűnő címsora mellett a 100vh többet mond a látható
          területnél, ettől a beviteli sor a képernyő alá lógott és az egész
          oldal görgethetővé vált (a felhasználó hibajelzése: "szét van esve",
          "mindig leteker"). Így a chat pontosan a látható területet tölti ki,
          és csak az üzenetlista görög. */}
      <div className="flex-1 p-3 md:p-8">
        <Card title="AI Assistant" className="flex h-[calc(100dvh-92px)] flex-col !p-4 md:h-[calc(100dvh-160px)] md:!p-6">
          <AiAssistantChat />
        </Card>
      </div>
    </div>
  );
}
