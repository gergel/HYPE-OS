"""HOGYAN mozgott a pénz - és mennyi készpénz van emiatt a kasszában.

Minden kiadásnál és bevételnél megadható, milyen úton ment/jött a pénz. Ez nem
könyvelési finomság: a KÉSZPÉNZ egy fizikai doboz, aminek van egyenlege, és azt
csak akkor tudjuk, ha minden készpénzes tétel meg van jelölve. Az utalás és a
bankkártya a bankszámlát mozgatja, a kasszát nem.

    kassza egyenleg = a készpénzes BEVÉTELEK - a készpénzes KIADÁSOK

A lista SZÁNDÉKOSAN zárt és egy helyen áll: ha mindenki maga írja be ("kp",
"készpénz", "KP"), akkor az összesítés annyi felé szakad, ahányféleképp
leírták - és a kassza egyenlege pont annyival lesz hamis.
"""

from __future__ import annotations

from typing import Any

from app.services.hu_szoveg import ekezet_nelkul

KESZPENZ = "Készpénz"
ATUTALAS = "Átutalás"
BANKKARTYA = "Bankkártya"

#: KIADÁSNÁL mind a három út járható: a céges kártyával fizetett tétel sem a
#: kasszából, sem külön utalással nem megy.
KIADAS_MODOK: tuple[str, ...] = (KESZPENZ, ATUTALAS, BANKKARTYA)

#: BEVÉTELNÉL kettő: vagy kézbe kapjuk (kassza), vagy a számlára érkezik.
#: Bankkártyás fizetés nálunk nincs - nem fogadunk kártyát, a terminálos
#: bevétel a Krumpellóé, annak saját, napi kassza-zárása van (lásd
#: models/krumpello.py).
BEVETEL_MODOK: tuple[str, ...] = (KESZPENZ, ATUTALAS)

#: Amit készpénznek ismerünk el. A Notionből örökölt sorokon "KP" és "Kp." is
#: előfordul, és mind ugyanazt jelenti.
#:
#: A "készpénz" ÉKEZETES alak nem duplikátum: a Pythonos út ékezet nélkül
#: hasonlít (lásd keszpenzes), az SQL-es viszont csak kisbetűsít (nincs minden
#: telepítésen ékezet-eltávolító függvény), tehát ott az ékezetes alak az, ami
#: ténylegesen illeszkedik.
KESZPENZ_ALAKOK: frozenset[str] = frozenset({"keszpenz", "készpénz", "kp", "kp.", "cash"})


def keszpenzes(mod: Any) -> bool:
    """Készpénzben mozgott-e ez a tétel? Üres/ismeretlen mód: NEM.

    Az üres nem "talán": ha nincs megjelölve, nem tudjuk, tehát nem is
    számoljuk bele a kasszába. Egy találgatott egyenleg rosszabb, mint egy
    hiányos - az utóbbin legalább látszik, mennyi tétel nincs megjelölve."""
    if mod is None:
        return False
    return ekezet_nelkul(str(mod)) in KESZPENZ_ALAKOK


def keszpenz_sql(oszlop):
    """Ugyanez SQL-ben - az összesítők ebből szűrnek.

    A Pythonos és az SQL-es alak PÁRBAN van: ha az egyik változik, a másikat is
    állítani kell, különben a lista mást mutatna, mint az egyenleg."""
    from sqlalchemy import func

    # Az adatbázisban nincs ékezet-eltávolító függvény minden telepítésen,
    # ezért a néhány tényleges alakot soroljuk fel kisbetűsítve.
    return func.lower(func.coalesce(oszlop, "")).in_(sorted(KESZPENZ_ALAKOK))


#: Amit a kiadás TÍPUSÁBÓL/nevéből egyértelműen fel lehet ismerni.
#:
#: Honnan van erre egyáltalán esély? A Notionben a projekt kiadásoknál a
#: "Kiadás formája" mező (nálunk `Expense.tipus`) keveri a kiadás FAJTÁJÁT és a
#: fizetés ÚTJÁT: van benne "Bérlés" és "Alap bér", de van "Bankkártya" és
#: "Előfizetés" is. Az utóbbiak maguk mondják meg, hogyan mozgott a pénz.
#:
#: Két külön lista, mert a két kérdés más:
#:
#: - a KULCSSZAVAK bárhol állhatnak a szövegben, ezért csak olyan szó lehet
#:   köztük, ami mást nem jelenthet: az "Előfizetés – Adobe" ugyanúgy
#:   előfizetés, mint a puszta "Előfizetés";
#: - a TELJES EGYEZÉSEK rövid, kategória-szerű nevek ("Alap bér"), amiket
#:   viszont NEM szabad részletként keresni: a "bér" benne van a
#:   "Kamerabérlés"-ben is, ami épp nem munkabér, a "kártya" pedig az "SD
#:   kártya" eszközben.
#:
#: Az előfizetés azért mindig bankkártya, mert azokat kártyáról vonják - nincs
#: is hozzá utalás, amit indítani kellene. Az alap bér pedig azért átutalás,
#: mert a munkabér a bankszámlára megy.
KULCSSZO_MODOK: tuple[tuple[str, str], ...] = (
    ("elofizetes", BANKKARTYA),
    ("bankkartya", BANKKARTYA),
    ("kartyas", BANKKARTYA),
    ("keszpenzben", KESZPENZ),
    ("keszpenzes", KESZPENZ),
    ("atutalas", ATUTALAS),
    ("atutalva", ATUTALAS),
)

TELJES_EGYEZES_MODOK: dict[str, str] = {
    "alap ber": ATUTALAS,
    "alapber": ATUTALAS,
    "ber": ATUTALAS,
    "berek": ATUTALAS,
    "munkaber": ATUTALAS,
    "fizetes": ATUTALAS,
    "utalas": ATUTALAS,
    "kartya": BANKKARTYA,
    "keszpenz": KESZPENZ,
    "kp": KESZPENZ,
    "kp.": KESZPENZ,
    # A VALÓDI adatból: ezek a "Kiadás formája" értékek maradtak felismeretlenül
    # az első futás után, a hozzájuk tartozó módot pedig megmondták. Egyik sem
    # tippelhető ki a szóból - azért állnak itt, felsorolva.
    #
    # A "belsos"/"extra" a Kiadások tábla saját típusa (nem a Notion "Kiadás
    # formája"), lásd notion_import/importers_wave2.import_expenses: a belsősök
    # bére és a céges extra kiadás egyaránt utalással megy.
    "belsos": ATUTALAS,
    "extra": ATUTALAS,
    "forgatas": ATUTALAS,
    "elszamolasbol levonva": ATUTALAS,
    "altalanos tulora": ATUTALAS,
    "plusz napok": ATUTALAS,
    "starlink": ATUTALAS,
    # ELGÉPELT Notion-érték ("Előfizetls"), és épp ezért nem illeszkedett az
    # "elofizetes" kulcsszóra. Utalás - ezek a sorok nem kártyáról mennek.
    "elofizetls": ATUTALAS,
}


def kikovetkeztetett_mod(*szovegek: Any) -> str | None:
    """Mi lehet a fizetési mód a kiadás nevéből/típusából? None, ha nem tudjuk.

    A Notionből örökölt kiadásoknál a NÉV maga a válasz: "Alap bér",
    "Bankkártya", "Előfizetés". Ez a függvény ezt olvassa ki - a
    visszamenőleges kitöltéshez (lásd scripts/fizetesi_mod_kitoltese.py).

    Ami nem ismerhető fel egyértelműen, arra NONE-t ad: egy tippelt fizetési
    mód a kassza egyenlegét hazudná meg, márpedig épp azért van ez a mező."""
    for szoveg in szovegek:
        if not szoveg:
            continue
        tiszta = ekezet_nelkul(str(szoveg))
        if tiszta in TELJES_EGYEZES_MODOK:
            return TELJES_EGYEZES_MODOK[tiszta]
    for szoveg in szovegek:
        if not szoveg:
            continue
        tiszta = ekezet_nelkul(str(szoveg))
        for kulcsszo, mod in KULCSSZO_MODOK:
            if kulcsszo in tiszta:
                return mod
    return None
