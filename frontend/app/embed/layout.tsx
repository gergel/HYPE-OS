import { ConfirmProvider } from "@/components/ConfirmProvider";
import { ToastProvider } from "@/components/ToastProvider";

/** Az /embed/* útvonalak felugró ablakba (iframe-be) szánt, alkalmazás-keret
 * NÉLKÜLI nézetek - nincs oldalsáv és nincs felső sáv, mert azok a beágyazó
 * oldalon már ott vannak, és az iframe-en belül megismételve zavaróak lennének.
 *
 * A Toast/Confirm providerek viszont KELLENEK: ezek egyébként az (app)
 * layoutban élnek, ide viszont nem ér el, és nélkülük a beágyazott tartalom
 * minden megerősítést kérő gombja (törlés, diszpó küldés, feldarabolás)
 * hibára futna a useConfirm/useToast hívásnál. */
export default function EmbedLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <div className="flex min-h-screen flex-col">{children}</div>
      </ConfirmProvider>
    </ToastProvider>
  );
}
