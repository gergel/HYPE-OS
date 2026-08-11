// Barion Full Pixel esemény-segédek.
// A Base Pixelt a publikus portál tölti be (components/media-portal/BarionPixel.tsx) -
// SZÁNDÉKOSAN csak ott, a belső HYPE OS oldalakon nem követünk semmit.
// Ezek a függvények a vásárlási folyamat eseményeit küldik.

type BpFn = (action: string, event: string, data?: unknown) => void;

function bp(): BpFn | null {
  if (typeof window === "undefined") return null;
  const fn = (window as unknown as { bp?: BpFn }).bp;
  return typeof fn === "function" ? fn : null;
}

// Egy csomag tétel-objektuma a Barion contents formátumában.
// A gross a bruttó ár (Ft). A csomag "termékként" jelenik meg.
function packageContent(code: string, label: string, gross: number) {
  return {
    contentType: "Product",
    currency: "HUF",
    id: code,
    name: label,
    quantity: 1.0,
    unit: "db",
    unitPrice: gross,
    totalItemPrice: gross,
    category: "Tárhely-hosszabbítás",
  };
}

// Oldalmegtekintés — a portál betöltésekor
export function pixelContentView(title: string) {
  const fn = bp();
  if (!fn) return;
  fn("track", "contentView", {
    contentType: "Page",
    name: title || "HypeClient portál",
  });
}

// Fizetés indítása — amikor a néző a csomagra kattint (step 1)
export function pixelInitiateCheckout(code: string, label: string, gross: number) {
  const fn = bp();
  if (!fn) return;
  fn("track", "initiateCheckout", {
    contents: [packageContent(code, label, gross)],
    step: 1,
    currency: "HUF",
    revenue: gross,
  });
}

// Sikeres vásárlás — a fizetés után (a portál visszairányításkor)
export function pixelPurchase(
  code: string,
  label: string,
  gross: number,
  paymentId: string
) {
  const fn = bp();
  if (!fn) return;
  fn("track", "purchase", {
    contents: [packageContent(code, label, gross)],
    currency: "HUF",
    revenue: gross,
    orderId: paymentId,
  });
}

// Süti-hozzájárulás — a felhasználó elfogadta a marketing sütiket.
// Ezt a grantConsent eseményt a Barion Full Pixelhez el kell küldeni,
// hogy a Pixel marketing célú adatokat is küldhessen.
export function pixelGrantConsent() {
  const fn = bp();
  if (!fn) return;
  fn("consent", "grantConsent", {});
}

// A felhasználó elutasította — visszavonjuk a hozzájárulást.
export function pixelRejectConsent() {
  const fn = bp();
  if (!fn) return;
  fn("consent", "rejectConsent", {});
}
