"""A megrendelői SZÁMLA lépése egy projektkódon: határidő → kifizetve → bevétel.

Ez a papírozás harmadik (utolsó) lépése, a szerződés és a TIG után. Ugyanaz a
menet, mint az alvállalkozói oldalon (lásd routes/performance_certificates.py),
csak a másik irányba: ott mi fizetünk, itt minket fizetnek.

    számla feltöltése -> FIZETÉSI HATÁRIDŐ -> "Kifizetve" (a kifizetés napjával)
                                                 \\-> bevétel-sor a Pénzügyekben
                                                 \\-> vagy: indokolt kihagyás

MIÉRT KÖTELEZŐ A HATÁRIDŐ a kifizetés előtt? Mert a határidő az egyetlen dolog,
amiből látszik, hogy egy még ki nem fizetett számla KÉSIK-e. Ha csak a kifizetés
napját rögzítenénk, a lejárt számlák pont addig lennének láthatatlanok, amíg
számít.

A BEVÉTEL-SOR azért keletkezik automatikusan, mert a pénz megérkezése és a
Pénzügyek két külön felület volt: a projektkódon ki lett pipálva a kifizetés, a
bevételek közé viszont valakinek kézzel kellett felvezetnie - és ha elmaradt, a
projekt profitja hazudott.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_attachment import DocumentAttachment
from app.models.finance import Revenue
from app.models.project_code import ProjectCode
from app.services import penznem as penznem_szolg
from app.services import projektkod_osszeg

#: Az így keletkezett bevétel-sor megjegyzése - ebből látszik, hogy nem kézzel
#: vezették fel, hanem a számla-lépés zárásakor jött létre.
BEVETEL_MEGJEGYZES = "A megrendelői számla kifizetésekor keletkezett."


class SzamlaHiba(ValueError):
    """A művelet nem végezhető el - a felület ezt az üzenetet mutatja."""


@dataclass
class SzamlaAllas:
    """Hol tart a számla-lépés - ezt mutatja a projektkód "3. Számla" kártyája."""

    fizetesi_hatarido: date | None
    kifizetes_datuma: date | None
    kifizetve: bool
    bevetelbe_ne_keruljon: bool
    bevetel_kihagyas_oka: str | None
    #: A számlából adódó összeg (a papírokról vagy a projektkódról), a
    #: projektkód pénznemében.
    netto: float | None
    brutto: float | None
    #: Van-e feltöltött számla-fájl, és hol.
    van_szamla_fajl: bool
    #: A számla PDF-je - a csatolmányból, vagy a Notionból örökölt címről. A
    #: régi projektkódoknál gyakran csak ez utóbbi van meg, és ha nem írnánk
    #: ki, a "megvan a számla" állítás mögött nem lenne megnyitható papír.
    szamla_url: str | None
    #: Keletkezett-e bevétel-sor (és mennyi).
    bevetel_sorok: int
    #: "Erről a munkáról nincs számla" - ilyenkor határidő sincs, de kifizetve
    #: lehet (lásd _hatarido_kell).
    szamla_kihagyva: bool = False
    szamla_kihagyas_oka: str | None = None
    #: Kell-e fizetési határidő a kifizetés jelöléséhez. A felület ebből tudja,
    #: mikor tiltsa a gombot, és mikor rejtse el a határidő-mezőt.
    hatarido_kell: bool = True
    #: Milyen pénznemben vállaltuk, és milyen árfolyamon számolunk - devizás
    #: munkánál a bevétel ezzel átváltva, FORINTBAN kerül a Pénzügyekbe (lásd
    #: services/penznem.py). Forintos munkánál a *_forintban ugyanaz, mint a
    #: netto/brutto.
    penznem: str = "HUF"
    arfolyam: float | None = None
    netto_forintban: float | None = None
    brutto_forintban: float | None = None


def _szamla_fajl_url(db: Session, pk: ProjectCode) -> str | None:
    """A projektkódhoz feltöltött számla - a csatolmányokból, különben a
    Notionból örökölt URL-ből."""
    fajl = db.scalars(
        select(DocumentAttachment)
        .where(
            DocumentAttachment.entity_type == "projectCode",
            DocumentAttachment.entity_id == pk.id,
            DocumentAttachment.kategoria == "szamla",
        )
        .order_by(DocumentAttachment.id.desc())
    ).first()
    if fajl is not None:
        return fajl.url
    return pk.szamla_url if isinstance(pk.szamla_url, str) and pk.szamla_url else None


def _osszeg(pk: ProjectCode) -> tuple[float | None, float | None]:
    """(nettó, bruttó) - a közös szabály szerint (lásd
    services/projektkod_osszeg.py): TIG → szerződés → a projektkód mezői."""
    return projektkod_osszeg.szamlazott_osszeg(pk)


def _hatarido_kell(pk: ProjectCode) -> bool:
    """Kell-e fizetési határidő a kifizetés jelöléséhez?

    Alapból IGEN: a határidő az egyetlen dolog, amiből látszik, hogy egy még
    ki nem fizetett számla késik-e.

    NEM kell viszont ott, ahol nincs is számla: mert kimondtuk
    (szamla_kihagyva), mert az egész munka papír nélkül van elszámolva
    (papir_nelkul - nincs szerződés, nincs TIG, nincs számla), vagy mert az
    esemény ELMARADT (nem történt meg, tehát nincs miről számlázni).
    Egy nem létező számlának nincs határideje, és egy kitalált dátum
    rosszabb, mint a hiánya."""
    return not (pk.szamla_kihagyva or pk.papir_nelkul or pk.elmaradt)


def allas(db: Session, pk: ProjectCode) -> SzamlaAllas:
    netto, brutto = _osszeg(pk)
    netto_ft, brutto_ft = projektkod_osszeg.forintban(pk)
    szamla_url = _szamla_fajl_url(db, pk)
    return SzamlaAllas(
        fizetesi_hatarido=pk.fizetesi_hatarido,
        kifizetes_datuma=pk.utalas_datuma,
        kifizetve=pk.bevetel_kifizetve,
        bevetelbe_ne_keruljon=pk.bevetelbe_ne_keruljon,
        bevetel_kihagyas_oka=pk.bevetel_kihagyas_oka,
        netto=netto,
        brutto=brutto,
        penznem=penznem_szolg.normalizald(pk.penznem),
        arfolyam=float(pk.arfolyam) if pk.arfolyam is not None else None,
        netto_forintban=netto_ft,
        brutto_forintban=brutto_ft,
        van_szamla_fajl=szamla_url is not None,
        szamla_url=szamla_url,
        bevetel_sorok=len(list(pk.revenues or [])),
        szamla_kihagyva=pk.szamla_kihagyva,
        szamla_kihagyas_oka=pk.szamla_kihagyas_oka,
        hatarido_kell=_hatarido_kell(pk),
    )


def allitsd_a_hataridot(db: Session, pk: ProjectCode, hatarido: date | None) -> SzamlaAllas:
    """A számlán szereplő fizetési határidő. Törölni csak addig lehet, amíg a
    számla nincs kifizetve - utána az adat a bevétel-sorra is átment."""
    if hatarido is None and pk.utalas_datuma is not None:
        raise SzamlaHiba("A számla már ki van fizetve, a határidő nem törölhető.")
    pk.fizetesi_hatarido = hatarido
    # A már meglévő bevétel-soron is javítjuk, ha ott még nem volt megadva:
    # ugyanannak a számlának nem lehet két különböző határideje.
    for sor in pk.revenues or []:
        if sor.fizetes_hatarideje is None:
            sor.fizetes_hatarideje = hatarido
    db.flush()
    return allas(db, pk)


def jelold_kifizetettnek(
    db: Session,
    pk: ProjectCode,
    *,
    kifizetes_datuma: date | None = None,
    bevetelbe_ne_keruljon: bool = False,
    kihagyas_oka: str | None = None,
) -> SzamlaAllas:
    """"Kifizetve" - a pénz megérkezett.

    A KIFIZETÉS NAPJA kötelező. Korábban üresen hagyva a mai nap került be,
    csakhogy a jelölés ritkán esik egybe a beérkezéssel: a pénz megjön, és csak
    napokkal (néha hetekkel) később kattint rá valaki. A "mai nap" ilyenkor
    nem hiányzó adat pótlása, hanem egy CSENDBEN BEÍRT rossz dátum - és mivel
    ebből lesz a bevétel-sor dátuma, a bevétel rossz napra, rosszabb esetben
    rossz hónapra kerül. A dátum utólag nem is tűnik fel senkinek: nem üres,
    csak nem igaz.

    Alapesetben bevétel-sort is nyit (vagy kiegészíti a meglévőt), hogy a
    Pénzügyekben is ott legyen. Ha a hívó azt mondja, hogy ez a tétel nem való
    a bevételek közé, akkor INDOK kell hozzá - a sor ilyenkor is létrejön, csak
    az éves bevételbe nem számít (lásd services/elszamolas.py)."""
    if kifizetes_datuma is None:
        raise SzamlaHiba("Add meg, MIKOR érkezett meg a pénz - enélkül a bevétel rossz napra kerülne.")
    if pk.fizetesi_hatarido is None and _hatarido_kell(pk):
        raise SzamlaHiba(
            "Előbb add meg a számlán szereplő fizetési határidőt - enélkül nem látszik, ha egy számla késik. "
            "Ha erről a munkáról nincs számla, jelöld be a \"Nincs számla\" lehetőséget."
        )
    if bevetelbe_ne_keruljon and not (kihagyas_oka or "").strip():
        raise SzamlaHiba("Ha nem kerül a bevételek közé, írd meg, miért (beszámítva, máshol könyvelve…).")

    nap = kifizetes_datuma
    pk.utalas_datuma = nap
    pk.bevetelbe_ne_keruljon = bevetelbe_ne_keruljon
    pk.bevetel_kihagyas_oka = (kihagyas_oka or "").strip() or None if bevetelbe_ne_keruljon else None

    # Sor MINDKÉT esetben keletkezik - a különbség az, beleszámít-e az ÉVES
    # bevételbe. Korábban a kihagyott tételekről egyáltalán nem volt sor: a
    # pénzügyek listáján nyoma sem maradt annak, hogy az a munka rendezve van,
    # csak a projektkód adatlapján. Most ott a sor, láthatóan kihagyva
    # (lásd services/elszamolas.bevetel_beleszamit).
    _vezesd_fel_a_bevetelt(db, pk, nap, beleszamit=not bevetelbe_ne_keruljon)
    db.flush()
    return allas(db, pk)


def allitsd_a_szamla_kihagyast(
    db: Session, pk: ProjectCode, *, kihagyva: bool, oka: str | None = None
) -> SzamlaAllas:
    """"Erről a munkáról nincs számla" - be- és kikapcsolható, indokkal.

    Van, amit nem a megszokott módon fizetnek: beszámítás, csere, egy másik
    cégen át rendezett tétel. Ilyenkor nincs számla, tehát fizetési határidő
    sincs - a pénz viszont megjött (vagy másképp rendeződött), és a
    projektkódot le kell tudni zárni. Az INDOK azért kötelező, mert fél év
    múlva ez az egyetlen dolog, amiből kiderül, mi történt: enélkül csak
    annyi látszana, hogy erről az egy munkáról nincs papír."""
    if kihagyva and not (oka or "").strip():
        raise SzamlaHiba("Ha nincs számla, írd meg, miért (beszámítva, cserébe, másik cégen át…).")
    pk.szamla_kihagyva = kihagyva
    pk.szamla_kihagyas_oka = (oka or "").strip() or None if kihagyva else None
    db.flush()
    return allas(db, pk)


def _vezesd_fel_a_bevetelt(db: Session, pk: ProjectCode, nap: date, *, beleszamit: bool = True) -> None:
    """A bevétel-sor létrehozása/kiegészítése.

    Meglévő sort nem duplázunk (a Notionból importált bevételek már ott
    vannak): olyankor csak a hiányzó mezőket töltjük ki, és a kifizetés napját
    írjuk be. Új sort csak akkor nyitunk, ha egyáltalán nincs bevétel.

    A `beleszamit=False` azt jelenti: a pénz megjött, de nem ezen az úton
    (beszámítás, csere, másik cégen át) - a sor látszik, a projekt profitjában
    is benne van, csak az ÉVES bevételbe nem számít
    (lásd services/elszamolas.py)."""
    # A bevétel FORINTBAN kerül a rendszerbe, akkor is, ha a munkát euróban
    # vagy dollárban vállaltuk - az összesítők egy pénznemet ismernek (lásd
    # services/penznem.py). Az eredeti adat a soron marad, hogy fél év múlva is
    # látszódjon, miből lett.
    netto, brutto = projektkod_osszeg.forintban(pk)
    eredeti_netto, eredeti_brutto = _osszeg(pk)
    devizas = penznem_szolg.devizas(pk.penznem)
    szamla_url = _szamla_fajl_url(db, pk)
    sorok = list(pk.revenues or [])
    if not sorok:
        sor = Revenue(
            project_code_id=pk.id,
            netto=netto,
            brutto=brutto,
            penznem=penznem_szolg.FORINT,
            eredeti_penznem=penznem_szolg.normalizald(pk.penznem) if devizas else None,
            eredeti_netto=eredeti_netto if devizas else None,
            eredeti_brutto=eredeti_brutto if devizas else None,
            arfolyam=pk.arfolyam if devizas else None,
            megjegyzes=BEVETEL_MEGJEGYZES,
        )
        db.add(sor)
        sorok = [sor]

    for sor in sorok:
        if sor.fizetes_datuma is None:
            sor.fizetes_datuma = nap
        if sor.fizetes_hatarideje is None:
            sor.fizetes_hatarideje = pk.fizetesi_hatarido
        if not sor.bevetel_formaja and pk.bevetel_formaja:
            sor.bevetel_formaja = pk.bevetel_formaja
        if not sor.szamla_file_url and szamla_url:
            sor.szamla_file_url = szamla_url[:500]
        # A jelölést MINDIG felülírjuk (nem csak üresen): ez az adott
        # gombnyomás döntése, és visszavonáskor is vissza kell állnia.
        sor.beleszamit_a_bevetelekbe = None if beleszamit else False


def vond_vissza(db: Session, pk: ProjectCode) -> SzamlaAllas:
    """Mégsincs kifizetve - téves gombnyomás javítása.

    A bevétel-sort NEM töröljük (lehet, hogy máshonnan való, és a törlés
    visszahozhatatlan), csak a kifizetés dátumát vesszük ki róla - így a
    Pénzügyekben újra "kiállítva, még nem fizetve" lesz."""
    pk.utalas_datuma = None
    pk.bevetelbe_ne_keruljon = False
    pk.bevetel_kihagyas_oka = None
    for sor in pk.revenues or []:
        if sor.megjegyzes == BEVETEL_MEGJEGYZES or sor.fizetes_datuma is not None:
            sor.fizetes_datuma = None
        # A kihagyás jelölése is visszaáll: ha mégsincs kifizetve, nincs mit
        # kihagyni az éves bevételből (lásd services/elszamolas.py).
        if sor.beleszamit_a_bevetelekbe is False:
            sor.beleszamit_a_bevetelekbe = None
    db.flush()
    return allas(db, pk)
