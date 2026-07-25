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
        {/* Az "embed-root" osztály rejti el az alkalmazás-keretet (felső sáv,
            vissza-link) a beágyazott nézetben - lásd globals.css. Azért CSS-sel
            és nem feltételes rendereléssel, mert az /embed útvonalak
            SZÁNDÉKOSAN ugyanazt a page komponenst exportálják újra, mint a
            rendes oldalak (így nem tudnak elcsúszni egymástól), és azok maguk
            renderelik a saját fejlécüket. Az osztály már a szerver-oldali
            HTML-ben ott van, tehát nincs felvillanás. */}
        <div className="embed-root flex min-h-screen flex-col">{children}</div>
      </ConfirmProvider>
    </ToastProvider>
  );
}
