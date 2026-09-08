# Nagy portálletöltés – éles rendszerbe illesztve

A PR #2 a régi main scaffoldra készült. A Railwayen használt ág `claude/hype-os-project-scaffold-8nlgej`, kiinduló commit `44a96d1`. A PR közvetlen merge-je/deployja nem kompatibilis ezzel. A ZIP64 író és a streamelt S3 multipart réteg átvétele mellett az integráció a valódi Portal/PortalImage/PortalVideo modellekhez és a meglévő Celery workerhez készült.

## Viselkedés

Az Összes letöltése, Mappa letöltése és Fotók letöltése gomb tartós exportot indít. A böngésző állapotot kérdez, nem tölti memóriába az eredeti fájlokat. A kész archívum közvetlen R2 letöltésként indul. A csomag 48 órán keresztül újrahasználható; azonos kijelöléssel, az oldal újranyitása után is ugyanahhoz a munkához csatlakozik. A Bezárás a várakozást szakítja meg, a szerveroldali feladat folytatódik.

A jelszavas portál, megosztó link, csak egy mappára/videóra szóló link és rejtett tartalom szabályai a létrehozáskor és minden állapot/link lekéréskor érvényesülnek. A létrehozás fájlazonosítókat fogad, tetszőleges R2-kulcsokat nem. Hiányzó/hibás forrás esetén nem készül csonka sikeres csomag. Az eredeti objektumokat nem töröljük.

A forrás GET If-Match ETag alapján rögzített; utóellenőrzés és DB-verzióellenőrzés is történik. Minden workerpróbálkozás külön véletlen objektumkulcsra ír, és csak a saját DB-bérletét zárhatja sikeresre. A bérletet külön heartbeat tartja életben. A beat percenként helyreállítja a beragadt feladatokat és takarítja a lejárt exportokat. Maximum három automatikus próbálkozás, utána felhasználói újraindítás.

## Railway

A meglévő Backend, Worker és Frontend frissítendő; nincs új service, új bucket vagy új titok. A meglévő R2/Redis/Postgres konfigurációt használja. A worker start command változatlan: `celery -A app.workers.portal_tasks worker -B --loglevel=info --concurrency=2`.

Új migráció: `l8c5d96e3f17`, szülő `k7b4c85d2f06`. Kizárólag az új `portal_exports` táblát és indexeit hozza létre, meglévő sorokat/oszlopokat nem módosít. A backend meglévő indítása futtatja az Alembic upgrade-et.

## Ellenőrzés

- `PYTHONPATH=. python -m pytest tests/test_portal_exports.py -q`: 14 passed, 1 skipped (a valódi R2 teszt külön fut).
- Valódi R2: 50 331 648 forrásbájt, 50 332 026 bájtos ZIP64 archívum; multipart upload; letöltés első 1 MiB-ja után új link, Range/If-Range 206; teljes hash egyezés; minden kicsomagolt fájl hash egyezés. 1 passed. Kizárólag saját, véletlen prefixű tesztadatok, utána törölve.
- Teljes Next.js production build: sikeres.
- PostgreSQL: új migráció up/down/up és BIGINT típusok ellenőrizve egy tranzakción belüli elkülönített tesztsémában; a teljes tranzakció rollbackkel lezárva.

**50 GB teljes R2 export/letöltés még nincs lemérve.** A korábbi PR 5 GB lokális tesztje a ZIP64 maghoz ad bizonyítékot, de az nem azonos ennek az éles integrációnak az 50 GB-os végponttól végpontig tesztjével.

## Korlátok

A megosztott R2 bucket véletlen, nem listázott `portal-exports/<uuid>/<attempt-uuid>.zip` kulcsokat kap. A presigned URL egy óráig érvényes; kiadott URL-t ezen belül az objektumtár szolgál ki, nem a portál végzi az újbóli jogosultságellenőrzést. Megszakítás után új link ugyanarra a változatlan objektumra kérhető; a konkrét böngésző letöltésfolytatási viselkedése eltérhet. Nagy ZIP kibontásához megfelelő hely kell a felhasználó gépén. Egyszerre maximum négy aktív kijelölés portálonként, kérésenként legfeljebb 20 000 kép és 20 000 videó. A meglévő két Celery slotot használja, ezért sok hosszú export más háttérfeladatok indulását késleltetheti; nagy terhelésnél külön export queue/worker javasolt.
