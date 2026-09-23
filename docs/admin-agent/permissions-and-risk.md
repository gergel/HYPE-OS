# HYRON — jogosultság és kockázat

## Kockázati osztályok (szerver-oldali besorolás)

A kockázatot a SZERVER sorolja be; a modell nem minősítheti át saját műveletét
alacsonyabbra (lásd `app/admin_agent/executor.py` `ToolSpec.risk` és
`app/admin_agent/policy.py`).

| Osztály | Jelentés | Példa |
|---|---|---|
| R0 | Olvasás / belső javaslat, nincs mellékhatás | elemzés, javaslatkészítés |
| R1 | Ellenőrzötten visszafordítható belső írás | belső előkészítés |
| R2 | Külső kommunikáció vagy pénzügyi/jogi jelentőségű változás | számla-felvezetés, e-mail kiküldése |
| R3 | Tiltott művelet | banki utalás végrehajtása |

**R3 SOHA nem engedélyezhető** — a magasabb bizalmi szint sem oldja fel. Banki
utalást indító/aláíró/végrehajtó eszköz **nincs regisztrálva** (`TOOL_REGISTRY`).

## Bizalmi szintek (trust)

Feladattípus × altípus szinten (`aa_trust_policies`), a Beállítások oldalról
állítható (trust_change jog):

| Szint | Jelentés |
|---|---|
| L0 | Árnyék: csak elemzés/javaslat, nincs mellékhatás |
| L1 | Előkészítés, emberi véglegesítés (jóváhagyás-köteles) |
| L2 | Szigorúan körülhatárolt, alacsony kockázatú automatika |
| L3 | Munkasor-önállóság kivételkezeléssel, változatlan pénzügyi/jogi korlátokkal |
| L4 | Csak külön engedélyezett, alacsony kockázatú körben |

## A végrehajtási döntés (policy engine)

Az egyetlen döntéshozó a `policy.decide()`. Bemenet: kockázat, trust, modul-
kapcsoló, mellékhatás-kapcsoló, vészleállítás, altípus + auto-engedett altípusok.

- R3 → mindig **BLOCKED**.
- R0 → **AUTO** (nincs mellékhatás).
- R1/R2 esetén előbb a globális kapuk: vészleállítás / modul ki / mellékhatás
  tiltva → **BLOCKED**. L0 → **BLOCKED**.
- R1: L2+ → AUTO; L1 → NEEDS_APPROVAL.
- R2: alapból NEEDS_APPROVAL; **AUTO csak L3+ ÉS kifejezetten engedélyezett,
  alacsony kockázatú altípus** esetén.
- Ismeretlen kockázat → **BLOCKED** (fail-closed).

A döntést a rendszer a végrehajtás PILLANATÁBAN újra kiolvassa (nem korábbi
pillanatképből), minden hívási úton (worker, közvetlen API, retry).

## Végrehajtási guard-lánc (executor)

`execute_approved` sorrendje: jóváhagyás-hash kötés → javaslat-frissesség →
regisztrált eszköz → determinista validálás → policy ÚJRA → idempotens
lefoglalás (javaslatonként egy `aa_action_executions`, egyedi kulcs) → fencing
token → eszközhívás → audit. A mellékhatás csak akkor fut, ha a policy engedi;
egyébként a rekord `blocked`, és az eszköz nem hívódik meg.

## Jogosultságok (RBAC)

A modul az `/admin-agent` oldal jogát használja; minden szerepkör-kapu nyitva
(`_MINDEN_SZEREPKOR`), a valódi szűrést a `page_permissions` adja (mint az
Utómunka/Diszpó oldalaknál). A művelet→jog jelenlegi leképezés:

| Művelet | Jog |
|---|---|
| Nézés (overview, munkasor, napló, tudástár, eval...) | `view` |
| Feladat létrehozása / szerkesztése, javaslat, jóváhagyás/elutasítás, correction, analyze, distill/eval indítás | `edit` |
| Magas kockázatú kapcsolók (modul/mellékhatás/vészleállítás), szabály AKTIVÁLÁS, kiadás aktiválás, **bizalmi szint módosítás** | `delete` |

A finomabb, külön permissionök (financial_approve, legal_approve, rule_activate,
trust_change, audit_export) a jelenlegi durvább `edit`/`delete` leképezés felett
egy következő lépésben vezethetők be, ha az üzemeltetés igényli — a hozzájuk
tartozó ellenőrzési pontok (jóváhagyás, aktiválás, trust-váltás) már külön
végpontokon vannak.

**A fejlesztéshez használt hozzáférés és az éles HYRON jogosultságai külön
fogalmak.** A fejlesztői engedély nem éles üzleti végrehajtási engedély.

## Prompt injection és adatbiztonság

- E-mail, PDF, korábbi példa és külső szöveg **adat, nem utasítás**. Az onnan
  származó „hagyd figyelmen kívül / küldd el / emeld a limitet" tartalom nem ad
  jogosultságot: a korlátokat szerver-oldali eszköz-, címzett-, validálás- és
  policy-ellenőrzés kényszeríti ki, nem a modell ébersége.
- Automatikus/nem válaszolható címzettre (no-reply, mailer-daemon, bounce,
  postmaster) az e-mail eszköz determinista módon TILT — nincs körkörös hurok.
- A titkok/OAuth-tokenek a szerveren maradnak; az integráció-állapot csak
  „Kész / Beállítás szükséges", az érték nem kerül a böngészőbe.
- Egyszervezetes rendszer: nincs kereszt-szervezeti adatelérés; a hozzáférést a
  meglévő RBAC + rekordszintű szűrés adja a retrievalben is.
