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

HOGYAN érkezett a pénz, azt a jelöléskor kérdezzük meg (`fizetes_modja`), és
nem tippeljük:

- **átutalás**: a bankszámlára jött, a bevételek közé kerül;
- **készpénz**: a bevételek közé kerül, ÉS a KASSZÁBA is - a KP forgalom
  oldalon ugyanaz a sor jelenik meg, külön felvezetés nélkül (lásd
  services/kassza.py). Ezért NEM készül hozzá külön KpForgalom sor: az
  kétszer számolná ugyanazt a pénzt.

A készpénzes bevétel két félét jelenthet, és a különbséget a SZÁMLA dönti el
(lásd services/bizonylat.py):

- van mögötte számla -> sima LEGÁLIS bevétel;
- nincs mögötte számla -> FEDEZET: ez az a készpénz, amiből a számla nélküli
  kiadás fedezhető, tehát a fekete egyenleget csökkenti.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document_attachment import DocumentAttachment
from app.models.finance import Revenue
from app.models.project_code import ProjectCode
from app.services import bizonylat
from app.services import fizetesi_mod as fizetesi_mod_szolg
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
    #: Kötelező-e a kifizetés dátuma. Ahol számlát sem várunk, ott nem: a
    #: legtöbbször nincs is tranzakció (lásd _kifizetes_datum_kell).
    kifizetes_datum_kell: bool = True
    #: Tranzakció NÉLKÜL lett lezárva - ilyenkor nincs kifizetési dátum, és ez
    #: nem hiány, hanem maga a válasz.
    tranzakcio_nelkul_lezarva: bool = False
    #: Milyen pénznemben vállaltuk, és milyen árfolyamon számolunk - devizás
    #: munkánál a bevétel ezzel átváltva, FORINTBAN kerül a Pénzügyekbe (lásd
    #: services/penznem.py). Forintos munkánál a *_forintban ugyanaz, mint a
    #: netto/brutto.
    penznem: str = "HUF"
    arfolyam: float | None = None
    netto_forintban: float | None = None
    brutto_forintban: float | None = None
    #: HOGYAN érkezett a pénz (Átutalás / Készpénz). A készpénzes bevétel a
    #: kasszába is bekerül - lásd a modul leírását.
    fizetes_modja: str | None = None
    #: Készpénzes bevételnél: van-e mögötte számla. Ettől függ, hogy sima
    #: legális bevétel-e, vagy FEDEZET a számla nélküli kiadásokhoz.
    keszpenzes: bool = False
    van_szamla_a_bevetelen: bool = False
    #: MENNYI IDŐ van a kifizetésig, vagy mennyivel csúszott - a fizetési
    #: határidőhöz mérve (lásd models/project_code.hatarido_allas). Egy dátum
    #: önmagában néma: hogy sürgős-e, csak a mai naphoz képest derül ki.
    hatarido_allas: dict | None = None


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


def szamlat_varunk(pk: ProjectCode) -> bool:
    """Lesz-e egyáltalán SZÁMLA erről a munkáról?

    Három okból lehet nem: mert kimondtuk (`szamla_kihagyva`), mert az egész
    munka papír nélkül van elszámolva (`papir_nelkul` - nincs szerződés, nincs
    TIG, nincs számla), vagy mert az esemény ELMARADT (nem történt meg, tehát
    nincs miről számlázni).

    Ez a kérdés több helyen dönt, ezért áll egy helyen:

    - nincs fizetési határidő és nincs kifizetési dátum (lásd lentebb) - egy
      nem létező számlának nincs határideje, és egy kitalált dátum rosszabb,
      mint a hiánya;
    - a KIHAGYOTT papír itt nem hiányosság: ha nincs számla, nincs is mihez
      szerződést és TIG-et készíteni, tehát azok kihagyása következmény, nem
      elmaradás. A projektkód-lista "kihagyott papír" szűrője ezért ezeket
      nem hozza fel (lásd frontend components/ProjektkodPapirSzuro.tsx)."""
    return not (pk.szamla_kihagyva or pk.papir_nelkul or pk.elmaradt)


def _hatarido_kell(pk: ProjectCode) -> bool:
    """Kell-e fizetési határidő a kifizetés jelöléséhez?

    Alapból IGEN: a határidő az egyetlen dolog, amiből látszik, hogy egy még
    ki nem fizetett számla késik-e. Ahol viszont számlát sem várunk, ott nem
    (lásd szamlat_varunk)."""
    return szamlat_varunk(pk)


def _kifizetes_datum_kell(pk: ProjectCode) -> bool:
    """Kötelező-e megadni, MIKOR érkezett meg a pénz?

    Ugyanaz a szabály, mint a fizetési határidőnél (lásd _hatarido_kell): ahol
    számlát sem várunk, ott a legtöbbször pénzmozgás sincs. A munka
    beszámítódik valamibe, kompenzálódik, vagy elmaradt - ilyenkor a "mikor
    érkezett meg a pénz" kérdésre NINCS igaz válasz, és egy beírt dátum nem
    hiányzó adat pótlása lenne, hanem egy kitalált tranzakció.

    Ahol viszont számla van, ott a dátum továbbra is kötelező: abból lesz a
    bevétel-sor napja, tehát rossz hónapba is csúszhat a bevétel."""
    return _hatarido_kell(pk)


def _bevetel_fizetesi_modja(pk: ProjectCode) -> str | None:
    """A bevétel-sorok fizetési módja - ha egyöntetű. Több sornál (osztott
    számlázás) csak akkor mondunk módot, ha mind ugyanaz: két különböző mód
    közül választani helyettük találgatás volna."""
    modok = {(sor.fizetes_modja or "").strip() for sor in pk.revenues or []}
    modok.discard("")
    return next(iter(modok)) if len(modok) == 1 else None


def allas(db: Session, pk: ProjectCode) -> SzamlaAllas:
    netto, brutto = _osszeg(pk)
    netto_ft, brutto_ft = projektkod_osszeg.forintban(pk)
    szamla_url = _szamla_fajl_url(db, pk)
    mod = _bevetel_fizetesi_modja(pk)
    # A "fedezet vagy legális bevétel" kérdés csak KÉSZPÉNZNÉL merül fel, és a
    # SZÁMLA dönti el - ugyanaz a szabály, amiből a kassza is dolgozik.
    szamlas_bevetelek = bizonylat.szamlas_bevetel_ids(db) if fizetesi_mod_szolg.keszpenzes(mod) else set()
    return SzamlaAllas(
        fizetes_modja=mod,
        keszpenzes=fizetesi_mod_szolg.keszpenzes(mod),
        van_szamla_a_bevetelen=any(
            bizonylat.van_szamla_bevetel(sor, szamlas_bevetelek) for sor in pk.revenues or []
        ),
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
        kifizetes_datum_kell=_kifizetes_datum_kell(pk),
        tranzakcio_nelkul_lezarva=pk.tranzakcio_nelkul_lezarva,
        hatarido_allas=pk.hatarido_allas,
    )


def jelold_kifizetettnek(
    db: Session,
    pk: ProjectCode,
    *,
    kifizetes_datuma: date | None = None,
    bevetelbe_ne_keruljon: bool = False,
    kihagyas_oka: str | None = None,
    fizetes_modja: str | None = None,
) -> SzamlaAllas:
    """"Kifizetve" - a pénz megérkezett.

    Ha VAN kifizetés napja, azt sose tippeljük: korábban üresen hagyva a mai
    nap került be, csakhogy a jelölés ritkán esik egybe a beérkezéssel - a
    pénz megjön, és csak napokkal (néha hetekkel) később kattint rá valaki. A
    "mai nap" ilyenkor nem hiányzó adat pótlása, hanem egy CSENDBEN BEÍRT
    rossz dátum - és mivel ebből lesz a bevétel-sor dátuma, a bevétel rossz
    napra, rosszabb esetben rossz hónapra kerül. A dátum utólag nem is tűnik
    fel senkinek: nem üres, csak nem igaz.

    Alapesetben bevétel-sort is nyit (vagy kiegészíti a meglévőt), hogy a
    Pénzügyekben is ott legyen. Ha a hívó azt mondja, hogy ez a tétel nem való
    a bevételek közé, akkor INDOK kell hozzá - a sor ilyenkor is létrejön, csak
    az éves bevételbe nem számít (lásd services/elszamolas.py).

    A DÁTUM MINDIG elhagyható - nem csak ott, ahol számlát sem várunk. Üresen
    hagyva TRANZAKCIÓ NÉLKÜLI lezárás lesz belőle: a pénz nem valódi
    tranzakcióval jött (beszámítva, csere, másik cégen át rendezve), ezért
    SOSEM kerül bevétel-sorba, és MINDIG kér hozzá indokot - ez az egyetlen
    dolog, amiből fél év múlva kiderül, mi történt."""
    if kifizetes_datuma is None:
        if not (kihagyas_oka or "").strip():
            raise SzamlaHiba("Írd meg, miért nem volt tranzakció (beszámítva, csere, másik cégen át rendezve…).")
    elif bevetelbe_ne_keruljon and not (kihagyas_oka or "").strip():
        raise SzamlaHiba("Ha nem kerül a bevételek közé, írd meg, miért (beszámítva, máshol könyvelve…).")
    mod = (fizetes_modja or "").strip() or None
    if mod is not None and mod not in fizetesi_mod_szolg.BEVETEL_MODOK:
        raise SzamlaHiba(
            f"Ismeretlen fizetési mód: {mod}. Választható: {', '.join(fizetesi_mod_szolg.BEVETEL_MODOK)}."
        )

    if kifizetes_datuma is None:
        # TRANZAKCIÓ NÉLKÜLI LEZÁRÁS: nem volt pénzmozgás, tehát nincs dátum és
        # nincs bevétel-sor sem. A projektkód ettől még lezárt - a rendezés
        # ténye a jelölés (lásd models/project_code.tranzakcio_nelkul_lezarva).
        # A bevételekből való kihagyás itt MINDIG igaz - nem a hívóra bízzuk
        # (a felület úgyis mindig True-t küld ide, de a szerver a saját
        # szabályát nem a kliens szavára alapozza).
        pk.bevetelbe_ne_keruljon = True
        pk.bevetel_kihagyas_oka = kihagyas_oka.strip()
        pk.utalas_datuma = None
        pk.tranzakcio_nelkul_lezarva = True
        db.flush()
        return allas(db, pk)

    pk.bevetelbe_ne_keruljon = bevetelbe_ne_keruljon
    pk.bevetel_kihagyas_oka = (kihagyas_oka or "").strip() or None if bevetelbe_ne_keruljon else None

    nap = kifizetes_datuma
    pk.utalas_datuma = nap
    pk.tranzakcio_nelkul_lezarva = False

    # Sor MINDKÉT esetben keletkezik - a különbség az, beleszámít-e az ÉVES
    # bevételbe. Korábban a kihagyott tételekről egyáltalán nem volt sor: a
    # pénzügyek listáján nyoma sem maradt annak, hogy az a munka rendezve van,
    # csak a projektkód adatlapján. Most ott a sor, láthatóan kihagyva
    # (lásd services/elszamolas.bevetel_beleszamit).
    _vezesd_fel_a_bevetelt(db, pk, nap, beleszamit=not bevetelbe_ne_keruljon, fizetes_modja=mod)
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


def _vezesd_fel_a_bevetelt(
    db: Session, pk: ProjectCode, nap: date, *, beleszamit: bool = True, fizetes_modja: str | None = None
) -> None:
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
        # A KAPCSOLATON át adjuk hozzá, nem `db.add()`-del: így a projektkód
        # `revenues` gyűjteménye rögtön tud róla. Egy sima add() után a
        # visszaadott állapot (lásd allas) még a régi, ÜRES gyűjteményt látná -
        # vagyis a "Kifizetve" gombra kattintva a kártya azt válaszolná, hogy
        # "Fizetésre vár", és csak a következő betöltéskor javulna meg.
        pk.revenues.append(sor)
        sorok = [sor]

    for sor in sorok:
        if sor.fizetes_datuma is None:
            sor.fizetes_datuma = nap
        if sor.fizetes_hatarideje is None:
            sor.fizetes_hatarideje = pk.fizetesi_hatarido
        if not sor.bevetel_formaja and pk.bevetel_formaja:
            sor.bevetel_formaja = pk.bevetel_formaja
        # A FIZETÉSI MÓD a jelölés döntése, tehát felülírja a korábbit: aki
        # most mondta meg, hogy készpénzben jött, az tudja a legjobban. Ha nem
        # adták meg (régi hívás, script), a meglévő marad, üresen pedig az
        # alapértelmezés - egy jelöletlen sor se a kasszába, se a bankba nem
        # tartozna (lásd services/kassza._jeloletlen).
        if fizetes_modja:
            sor.fizetes_modja = fizetes_modja
        elif not (sor.fizetes_modja or "").strip():
            sor.fizetes_modja = fizetesi_mod_szolg.BEVETEL_ALAPERTELMEZES
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
    pk.tranzakcio_nelkul_lezarva = False
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


def _tobb_szamla_van(db: Session, pk: ProjectCode) -> bool:
    """Van-e ennél a projektkódnál egynél TÖBB feltöltött számla-fájl - ettől
    függ, hogy a fájlonkénti kifizetéshez kötelező-e a számla saját nettó
    összege (lásd jelold_szamlat_kifizetettnek)."""
    darab = db.scalar(
        select(func.count())
        .select_from(DocumentAttachment)
        .where(
            DocumentAttachment.entity_type == "projectCode",
            DocumentAttachment.entity_id == pk.id,
            DocumentAttachment.kategoria == "szamla",
        )
    )
    return (darab or 0) > 1


def jelold_szamlat_kifizetettnek(
    db: Session,
    doc: DocumentAttachment,
    pk: ProjectCode,
    *,
    kifizetes_datuma: date | None,
    netto: float | None,
    plusz_afa: bool,
    fizetes_modja: str | None,
    bevetelbe_ne_keruljon: bool,
    kihagyas_oka: str | None,
) -> DocumentAttachment:
    """Egy KONKRÉT feltöltött számla kifizetettnek jelölése - SAJÁT bevétel-
    sort nyit ennek a fájlnak (nem a projektkód egy közös sorát egészíti ki,
    mint a `jelold_kifizetettnek`), mert osztott számlázásnál (több számla egy
    projektkódon) mindegyiknek külön összege és külön kifizetési dátuma van.

    Ha a számlának nincs saját nettója megadva, a projektkód vállalási ára
    adja az összeget - ez csak akkor elég, ha ez az EGYETLEN számla; többnél a
    saját összeg kötelező, különben a bevétel-sorok összege nem adná ki a
    projektkód teljes bevételét.

    A DÁTUM csak akkor kötelező, ha a számla a bevételek közé kerül: ha
    kihagyjuk (`bevetelbe_ne_keruljon`), a legtöbbször pont azért marad ki,
    mert nincs is valódi tranzakció (beszámítás, valakinek a fizetéséből
    levonva…) - üresen hagyva TRANZAKCIÓ NÉLKÜLI lezárás lesz belőle, és nem
    nyílik bevétel-sor (ugyanaz a szabály, mint a projektkód-szintű
    `jelold_kifizetettnek`-nél)."""
    if bevetelbe_ne_keruljon and not (kihagyas_oka or "").strip():
        raise SzamlaHiba("Ha nem kerül a bevételek közé, írd meg, miért (beszámítva, máshol könyvelve…).")
    if kifizetes_datuma is None and not bevetelbe_ne_keruljon:
        raise SzamlaHiba(
            "Add meg, MIKOR érkezett meg a pénz - enélkül a bevétel rossz napra kerülne. "
            "Ha nem kerül a bevételek közé, a dátum elhagyható."
        )
    if netto is None and _tobb_szamla_van(db, pk):
        raise SzamlaHiba(
            "Ehhez a projektkódhoz több számla is tartozik - add meg, mekkora ennek a számlának a nettó összege."
        )

    if kifizetes_datuma is None:
        # TRANZAKCIÓ NÉLKÜLI LEZÁRÁS: nem volt pénzmozgás, tehát nincs dátum és
        # nincs bevétel-sor sem (lásd a projektkód-szintű megfelelőjét,
        # jelold_kifizetettnek).
        doc.kifizetve_datuma = None
        doc.tranzakcio_nelkul_lezarva = True
        doc.netto = netto
        doc.plusz_afa = plusz_afa if netto is not None else None
        doc.bevetelbe_ne_keruljon = True
        doc.bevetel_kihagyas_oka = (kihagyas_oka or "").strip() or None
        db.flush()
        return doc

    mod = (fizetes_modja or "").strip() or None
    if mod is not None and mod not in fizetesi_mod_szolg.BEVETEL_MODOK:
        raise SzamlaHiba(
            f"Ismeretlen fizetési mód: {mod}. Választható: {', '.join(fizetesi_mod_szolg.BEVETEL_MODOK)}."
        )

    if netto is not None:
        eredeti_netto, eredeti_brutto = netto, projektkod_osszeg.brutto(netto, plusz_afa)
    else:
        eredeti_netto, eredeti_brutto = _osszeg(pk)

    devizas = penznem_szolg.devizas(pk.penznem)
    if devizas:
        if pk.arfolyam is None:
            raise SzamlaHiba(
                "Add meg az árfolyamot a vállalási árnál - enélkül nem tudjuk, mennyi a bevétel forintban."
            )
        ft_netto = penznem_szolg.forintra(eredeti_netto, pk.arfolyam)
        ft_brutto = penznem_szolg.forintra(eredeti_brutto, pk.arfolyam)
    else:
        ft_netto, ft_brutto = eredeti_netto, eredeti_brutto

    sor = Revenue(
        project_code_id=pk.id,
        netto=ft_netto,
        brutto=ft_brutto,
        penznem=penznem_szolg.FORINT,
        eredeti_penznem=penznem_szolg.normalizald(pk.penznem) if devizas else None,
        eredeti_netto=eredeti_netto if devizas else None,
        eredeti_brutto=eredeti_brutto if devizas else None,
        arfolyam=pk.arfolyam if devizas else None,
        fizetes_datuma=kifizetes_datuma,
        fizetes_hatarideje=doc.fizetesi_hatarido,
        fizetes_modja=mod or fizetesi_mod_szolg.BEVETEL_ALAPERTELMEZES,
        szamla_file_url=doc.url[:500] if doc.url else None,
        beleszamit_a_bevetelekbe=False if bevetelbe_ne_keruljon else None,
        megjegyzes=BEVETEL_MEGJEGYZES,
    )
    # A KAPCSOLATON át adjuk hozzá, nem `db.add()`-del - ugyanaz az ok, mint
    # `_vezesd_fel_a_bevetelt`-nél: a projektkód `revenues` gyűjteménye rögtön
    # tudjon róla, ne csak a következő betöltéskor.
    pk.revenues.append(sor)
    db.flush()  # kell a sor.id a visszavonáshoz

    doc.kifizetve_datuma = kifizetes_datuma
    doc.tranzakcio_nelkul_lezarva = False
    doc.netto = netto
    doc.plusz_afa = plusz_afa if netto is not None else None
    doc.bevetelbe_ne_keruljon = bevetelbe_ne_keruljon
    doc.bevetel_kihagyas_oka = (kihagyas_oka or "").strip() or None if bevetelbe_ne_keruljon else None
    doc.revenue_id = sor.id
    db.flush()
    return doc


def vond_vissza_szamla_kifizetes(db: Session, doc: DocumentAttachment) -> DocumentAttachment:
    """Egy fájlonkénti kifizetés-jelölés visszavonása - ugyanaz a szabály, mint
    a `vond_vissza`-nál: a hozzá nyitott bevétel-sort NEM töröljük, csak a
    kifizetés dátumát vesszük ki róla."""
    if doc.revenue_id is not None:
        sor = db.get(Revenue, doc.revenue_id)
        if sor is not None:
            sor.fizetes_datuma = None
            if sor.beleszamit_a_bevetelekbe is False:
                sor.beleszamit_a_bevetelekbe = None
    doc.kifizetve_datuma = None
    doc.tranzakcio_nelkul_lezarva = False
    doc.bevetelbe_ne_keruljon = False
    doc.bevetel_kihagyas_oka = None
    db.flush()
    return doc
