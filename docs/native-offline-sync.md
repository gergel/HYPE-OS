# Offline szerkesztés a natív appban

A kliens titkosított, fiókonként elkülönített helyi másolatot és tartós mentési sort használ. Korábbi online belépés után az app internet nélkül újranyitható. A már letöltött oldalak olvashatók; meglévő adatlapok támogatott PATCH-mezői és a diszpótábla cellái szerkeszthetők. Első belépés, új rekord, törlés, fájlfeltöltés, AI és külön jóváhagyási műveletek internetet igényelnek.

A kapcsolat visszatérésekor a kliens hitelesítést és jogosultságot ellenőriz, majd sorban újraküldi a mentéseket. A GET /api/v1/offline/capabilities jelzi a támogatott PATCH-végpontokat. A PATCH `_offline` mezője az eredeti mezőértékeket tartalmazza. A rekordzár és az előfeltételek ellenőrzése megakadályozza mások módosításainak felülírását. Elveszett válasz után az ismétlés nem futtatja újra a már alkalmazott módosítás mellékhatásait. Ütközéskor a helyi változat megmarad, a kliens szinkronpaneljén másolható és kezelhető.

A régi szerveren a kliens megőrzi a várakozó mentéseket, de nem indít ellenőrizetlen visszajátszást. A bővítésnek nincs új migrációja vagy környezeti változója; a korábbi push-javítás telepítési feltételei változatlanok. A Railway által ténylegesen telepített commitot külön ellenőrizni kell.

Ellenőrzés: 49 izolált szerverteszt (offline előfeltételek, idempotencia, generált CRUD-végpont, táblázatütközés és APNs-küldés). Swift helyi tárolási és szerkesztési tesztek sikeresek; macOS build és iOS típusellenőrzés sikeres. Valós iPhone-on, hálózatváltással végzett teljes folyamatellenőrzés még szükséges.
