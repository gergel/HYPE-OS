# HYPE OS ("HYPE Brain") – Termékspecifikáció

*A tartalom teljes egészében a `hype_os_kapcsolati_abra.mermaid`-ban feltérképezett 18 entitásra és a 17 Railway repóban talált, már működő logika **mintájára** épül – de a megvalósítás egy vadonatúj, önálló GitHub repóban, nulláról készül, semmilyen meglévő kódra nem építve.*

---

## 1. Termékvízió és fő célok

**Termékvízió:** A HYPE OS egy belső, videóprodukciós működésre szabott operatív rendszer, ami kiváltja a jelenlegi Notion + 17 Railway-szolgáltatás összeragasztott architektúráját egyetlen, natív PostgreSQL-alapú rendszerrel. Nem SaaS-termék, nem multi-tenant – kizárólag a HYPE (és a ContentBee márka) napi működésére.

**Fő célok:**
- Egyetlen igazság-forrás (jelenleg 43 Notion tábla + 3 különálló Railway Postgres között oszlik meg az adat)
- A törékeny, név-alapú relation-matching kiváltása valódi foreign key-ekkel
- A 7 klónozott dokumentum-generáló szolgáltatás egyetlen paraméterezett Automation modullá vonása
- Az already működő, jó logika (equipment ütközés-detektálás, diszpó email-szál kezelés, portál+fizetés) megtartása és natívra kötése
- Önköltség-számítás (ki mennyibe kerül egy forgatáson/vágáson) valós idejű, automatikus kimutatása

**Fő modulok** (a projektindító doksi saját sorrendje szerint, priorizálva):

| # | Modul | Forrás/logika |
|---|---|---|
| 1 | Auth | új, szerepkörökkel (admin / operatőr / vágó / ügyfél) |
| 2 | Dashboard | új |
| 3 | Clients | új (eddig nem volt önálló entitás, csak beágyazott mezők) |
| 4 | Project Codes | HYPE ADMIN projektkódok logikája alapján, új implementáció |
| 5 | Projects | Main Database (144 mezős monolit) logikája alapján, szétbontva |
| 6 | Crew (Employee + Rate) | Külsős és belsős + Vágók + Külsős + Belsős + Kreatív team + Hype Stáb + Órabér/napibér logikája alapján |
| 7 | Equipment | Leltár + Leltárak + Leltár tételek + Archive technika logikája, a `HYPE_Technika` ütközés-detektáló mintája alapján újraírva |
| 8 | Timeline | új (esemény-napló minden entitáshoz) |
| 9 | Storage | új, Cloudflare R2-vel |
| 10 | Portal | új, a projektindító doksi "Portal" fejezete alapján |
| 11 | Automation | a 7 dokumentum-generáló klón + diszpó + XP motor logikája, egyetlen új szolgáltatásba összevonva |
| 12 | Contracts | Keretszerződés + Alvállakozó keretszerződés logikája alapján |
| 13 | Finance (Expense/Revenue/KP forgalom) | Kiadások + Projekt kiadások + Bevételek + KP forgalom logikája alapján |
| 14 | Campaign | Kampányok logikája alapján, önállóan (nem kötve a Project Code maghoz) |
| 15 | AI Assistant | új, RAG réteg a végleges Postgres felett |

---

## 2. Információs architektúra (navigáció)

```
HYPE OS
├── Dashboard          (áttekintés, ma esedékes, figyelmeztetések)
├── Projektek
│   ├── Project Code-ok (pénzügyi egység, ügyfél, keret)
│   └── Projektek       (konkrét forgatások egy kódon belül)
├── Ügyfelek
│   ├── Clients         (cégek)
│   └── Contacts        (kapcsolattartók)
├── Csapat
│   ├── Crew / Employee (belsős, külsős, vágó, kreatív, stáb)
│   └── Rate            (bérezési szabályok)
├── Felszerelés
│   ├── Equipment        (asset + stock nézet)
│   └── Assignment       (kivitel/visszahozás, ütközés-jelzés)
├── Naptár / Diszpó
│   ├── Timeline          (projekt-eseménynapló)
│   └── Call Sheet        (diszpó)
├── Utómunka
│   ├── Deliverable       (vágandó anyag)
│   ├── Timesheet         (ledolgozott idő)
│   └── Feedback          (gombos visszajelzés)
├── Média & Portál
│   ├── Media/Folder      (feltöltött anyag)
│   ├── Portal            (ügyfél-nézet, jelszó/share link)
│   └── Payment           (Barion, opcionális)
├── Pénzügyek
│   ├── Expense / Revenue
│   ├── Contract          (keret / eseti)
│   └── KP forgalom       (önállóan)
├── Kampányok             (marketing, önálló ág)
├── Feladatok (Task)
├── AI Assistant
└── Beállítások
```

---

## 3. Adatbázis – a tényleges séma

A teljes, mezőszintű ER-diagram a `hype_os_kapcsolati_abra.mermaid` fájlban van (18 entitás). Ez a séma **helyettesíti** bármilyen generikus 7-táblás váltást – a HYPE-specifikus logikát (Project Code ≠ Project, Rate-alapú önköltség-számítás, asset vs. stock equipment, Contract altípusok) csak ez hordozza.

---

## 4. Backend architektúra

```
Next.js (frontend, új repó)
        │  /api
FastAPI (backend, új repó)
        │
┌───────┴────────────────────────────────────────────┐
│ Project Service │ Client Service │ Crew Service      │
│ Equipment Service (ütközés-detektálás, mintaként a HYPE_Technika alapján)│
│ Finance Service (önköltség-számítás: Rate×Timesheet) │
│ Automation Service (dokumentum-generálás egységesítve)│
│ Portal Service │ AI Service (később)       │
└───────┬────────────────────────────────────────────┘
        │
PostgreSQL (single source of truth) + Redis (cache/queue) + Cloudflare R2 (storage)
        │
Egyszeri, egyirányú Notion-import szkript (csak fejlesztés/teszt alatt, cutover-kompatibilis)
```

Ez a réteg **nem** hívja élőben a Notiont – a korábban egyeztetett döntés szerint a rendszer Notion-független, és csak egy alkalmankénti import-szkript hozza át a teszt-adatot, majd a végén a végleges cutover-adatot.

---

## 5. Automation modul – a 7 klón helyett 1 szolgáltatás

```
generate_document(entity_type, entity_id, document_kind)
    → sablon kiválasztása (TIG / eseti szerződés / keretszerződés, 7 típus)
    → PDF generálás
    → R2 feltöltés (Storage Service, nem közvetlen Drive-hívás)
    → Email (Notification modul, saját sablonokkal – diszpo-kuldes email-szál mintája alapján)
    → Contract/Expense/Employee entitás frissítése
    → Timeline Event rögzítése
```

Ide tartozik a diszpó két-fokozatú (előzetes/teljes) email-szál logikája és a XP/gamifikáció eseményvezérelt verziója is (`DeliverableApproved` → pontszámítás).

---

## 6. AI réteg (5. fázisban, a build roadmap szerint)

RAG-alapú asszisztens, ami a végleges Postgres felett tool-calling-gal dolgozik, nem közvetlen SQL-t ír (ahogy a projektindító doksi is előírja). Tervezhető funkciók:
- "Melyik eszköz szabad jövő héten?" → Equipment/Assignment lekérdezés
- "Mennyibe került az X forgatás eddig?" → Rate×Timesheet+Expense összesítés
- "Kinek jár még TIG ezen a projekten?" → Contract/Employee állapot lekérdezés

---

## 7. Roadmap

A részletes, fázisokra bontott terv a `hype_os_build_roadmap.md`-ban van (Fázis 0–4 az alaprendszer, Fázis 5 az AI réteg). Ez a dokumentum a tartalmi/funkcionális specifikáció hozzá – a kettő együtt adja a teljes tervet.

---

*Design/vizuális nyelv: a csatolt referenciakép stílusa (sötét téma, üveg-hatású kártyák, letisztult tipográfia) – tartalmi/funkcionális rész itt, vizuális mockup külön készül.*
