"""A megrendelői papírozás szabályai egy helyen.

Két kérdésre válaszol, és mindkettőt a projektkód felől nézi:

1. **Kell-e egyáltalán papír?** (`papirt_igenyel`)
2. **Kivel szerződünk, és milyen adatokkal?** (`szerzodo_fel_adatai`)

Azért van külön modul, mert ugyanezt a két kérdést a szerződés-oldal, a
TIG-oldal és a projektkód-adatlap is felteszi - három helyen leírva előbb-utóbb
három különböző válasz lenne belőle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client, Contact
from app.models.contract import Contract, ContractType, idoszak_tartalmazza
from app.models.megrendeloi_papir import MegrendeloiSzerzodes, MegrendeloiTig, papir_kesz
from app.models.project_code import ProjectCode


def megrendeloi_keret_ervenyes(szerzodes: Contract, nap: date | None = None) -> bool:
    """Érvényes-e ez a MEGRENDELŐI keretszerződés az adott napon?

    Miért nem a models/contract.keretszerzodes_ervenyes()? Mert az az
    ALVÁLLALKOZÓI oldalé: ott a `keretszerzodes` jelölő különbözteti meg a
    keretet az eseti megbízási szerződéstől, ezért a
    `megkotott_keretszerzodes()` kifejezetten `tipus == ALVALLALKOZOI`-t vár.
    Egy megrendelői keret `tipus`-a KERETSZERZODES, tehát azon a szűrőn sosem
    menne át - a "fedi-e a keret ezt a projektet" kérdésre mindig nem lenne a
    válasz, némán.

    Itt nincs mit szétválasztani: a megrendelői oldalon a típus MAGA a jelölő.
    Marad tehát a másik két feltétel: be van-e kapcsolva, és beleesik-e a nap
    valamelyik érvényességi időszakba. Ha egyetlen időszak sincs felvéve, a
    keret időbeli korlát nélkül érvényes - ugyanaz a szabály, mint az
    alvállalkozói oldalon."""
    if szerzodes.tipus != ContractType.KERETSZERZODES or not szerzodes.aktiv:
        return False
    idoszakok = list(szerzodes.idoszakok or [])
    if not idoszakok:
        return True
    return any(idoszak_tartalmazza(i, nap or date.today()) for i in idoszakok)


def papirt_igenyel(project_code: ProjectCode) -> bool:
    """Kell-e ehhez a projektkódhoz megrendelői szerződés és TIG?

    Három külön okból lehet nem:

    - **nincs szerződés** (`van_szerzodes = False`): a projekt nem szerződéses
      munka, tehát nincs mit papírozni;
    - **papír nélkül elszámolt** (`papir_nelkul`): a teljesítés ellenértéke nem
      pénzmozgással rendeződik (lásd models/project_code.py) - ott a papír nem
      elmaradt, hanem értelmezhetetlen;
    - **elmaradt az esemény** (`elmaradt`): a munka meg sem történt, tehát
      nincs mit igazolni. Ezt nem külön kapcsolóval kell jelölni, hanem az
      esemény állapotával - ott áll amúgy is, hogy elmaradt.

    A hármat szándékosan nem vonjuk össze egy mezőbe: az első azt mondja, hogy
    NINCS ügylet, a második azt, hogy VAN, csak másképp számolódik el, a
    harmadik azt, hogy MEG SEM TÖRTÉNT. A pénzügyi képük is más, és egy közös
    kapcsoló ezt elfedné."""
    return (
        bool(project_code.van_szerzodes)
        and not project_code.papir_nelkul
        and not project_code.elmaradt
    )


def keretszerzodes_fedi(db: Session, client_id: int | None, nap: date | None = None) -> Contract | None:
    """Van-e a megrendelővel ÉLŐ keretszerződésünk az adott napon?

    Ha van, az eseti szerződés elhagyható - a keret fedi. A TIG-et ez NEM
    váltja ki: a keretszerződés arról szól, milyen feltételekkel dolgozunk
    együtt, a TIG arról, hogy egy konkrét munka elkészült."""
    if client_id is None:
        return None
    keretek = db.scalars(
        select(Contract).where(
            Contract.tipus == ContractType.KERETSZERZODES,
            Contract.client_id == client_id,
        )
    ).all()
    return next((c for c in keretek if megrendeloi_keret_ervenyes(c, nap)), None)


@dataclass
class SzerzodoFel:
    """Akivel szerződünk - a papírra kerülő adatokkal.

    A mezők ELŐTÖLTÉSRE valók: a felületen mind szerkeszthető, és a mentéskor
    a papír a SAJÁT másolatát kapja (lásd models/megrendeloi_papir.py)."""

    client_id: int | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    kepviselo: str | None = None
    nyilvantartasi_szam: str | None = None
    email: str | None = None
    contact_id: int | None = None
    #: Ha keretszerződésből jött, annak az azonosítója.
    keretszerzodes_id: int | None = None
    #: Honnan származik: "keretszerzodes" | "ugyfel" | "kontakt" | "projektkod"
    forras: str = "ugyfel"


def _ugyfel_adatai(client: Client) -> SzerzodoFel:
    return SzerzodoFel(
        client_id=client.id,
        ceg_neve=client.nev,
        szekhely=client.szekhely,
        adoszam=client.adoszam,
        kepviselo=client.kepviselo,
        nyilvantartasi_szam=client.nyilvantartasi_szam,
        forras="ugyfel",
    )


def szerzodo_fel_adatai(
    db: Session,
    project_code: ProjectCode,
    *,
    client_id: int | None = None,
    contact_id: int | None = None,
    keretszerzodes_id: int | None = None,
) -> SzerzodoFel:
    """A papír előtöltése - a legjobb ismert forrásból.

    A sorrend a MEGBÍZHATÓSÁGOT követi, nem a kényelmet:

    1. **kifejezetten megadott keretszerződés** - azon a cégadatok már egyszer
       kimentek egy aláírt papíron, tehát azok a bizonyítottan jók;
    2. **kifejezetten megadott ügyfél** (a megrendelői kontaktok cége);
    3. **a projektkód ügyfele** - ez az alapeset;
    4. **a projektkódra Notionból örökölt megrendelő-mezők** - csak ha máshonnan
       semmi nincs. Ezek lapos szövegek import-korból: jobb, mint az üres
       papír, de nem tudjuk, mikor frissültek utoljára.

    A kontakt (ha van) csak az e-mail címet adja: a levél neki megy, de a
    cégadat a cégé."""
    fel: SzerzodoFel | None = None

    if keretszerzodes_id is not None:
        keret = db.get(Contract, keretszerzodes_id)
        if keret is not None:
            fel = SzerzodoFel(
                client_id=keret.client_id,
                ceg_neve=keret.ceg_neve or (keret.client.nev if keret.client else None),
                szekhely=keret.szekhely,
                adoszam=keret.adoszam,
                kepviselo=keret.vallalkozas_kepviseloje,
                nyilvantartasi_szam=keret.vallalkozas_nyilvantartasi_szam,
                email=keret.email,
                keretszerzodes_id=keret.id,
                forras="keretszerzodes",
            )

    if fel is None and client_id is not None:
        client = db.get(Client, client_id)
        if client is not None:
            fel = _ugyfel_adatai(client)

    if fel is None and project_code.client is not None:
        fel = _ugyfel_adatai(project_code.client)

    if fel is None:
        fel = SzerzodoFel(forras="projektkod")

    # A Notion-örökség csak a LYUKAKAT tölti ki - amit már tudunk, azt nem
    # írja felül: az ügyfél adatlapját karbantartják, ezeket a mezőket nem.
    fel.ceg_neve = fel.ceg_neve or project_code.megrendelo_neve
    fel.szekhely = fel.szekhely or project_code.megrendelo_szekhelye
    fel.adoszam = fel.adoszam or project_code.megrendelo_adoszama
    fel.kepviselo = fel.kepviselo or project_code.megrendelo_kepviseloje
    fel.nyilvantartasi_szam = fel.nyilvantartasi_szam or project_code.megrendelo_nyilvantartasi_szam

    # A kontakt az E-MAIL forrása: a levél egy embernek megy, nem egy cégnek.
    if contact_id is not None:
        kontakt = db.get(Contact, contact_id)
        if kontakt is not None:
            fel.contact_id = kontakt.id
            fel.email = kontakt.email or fel.email
            if fel.client_id is None:
                fel.client_id = kontakt.client_id
    if not fel.email:
        fel.email = _elso_email(project_code)

    # Ha a felhasználó nem adott meg keretszerződést, megnézzük, van-e élő -
    # a felület ebből írja ki, hogy "keretszerződés fedi".
    if fel.keretszerzodes_id is None:
        keret = keretszerzodes_fedi(db, fel.client_id, project_code.datum)
        if keret is not None:
            fel.keretszerzodes_id = keret.id
    return fel


def _elso_email(project_code: ProjectCode) -> str | None:
    """A projektkódra Notionból örökölt megrendelői e-mail lista első eleme.

    Szabad szöveg, vesszővel/pontosvesszővel/sortöréssel elválasztva - ezért
    nem szűrjük, csak az elsőt vesszük ki belőle: a cím helyességét úgyis a
    kiküldés előtti áttekintőn nézi meg valaki."""
    nyers = (project_code.megrendeloi_emailek or "").strip()
    if not nyers:
        return None
    for elvalaszto in (",", ";", "\n"):
        nyers = nyers.replace(elvalaszto, " ")
    reszek = [r.strip() for r in nyers.split() if "@" in r]
    return reszek[0] if reszek else None


@dataclass
class PapirAllas:
    """Egy projektkód papír-állása - ebből dolgozik a lista és az adatlap."""

    kell_papir: bool
    szerzodes: MegrendeloiSzerzodes | None
    tig: MegrendeloiTig | None
    #: Fedi-e a munkát ÉLŐ megrendelői keretszerződés. Ha igen, eseti szerződés
    #: nem kell - a keret megmondja, milyen feltételekkel dolgozunk együtt.
    keret_fedi: bool = False

    @property
    def szerzodes_kesz(self) -> bool:
        return papir_kesz(self.szerzodes)

    @property
    def szerzodes_kell(self) -> bool:
        """Kell-e EGYEDI (eseti) szerződés erre a projektkódra.

        Élő keretszerződés alatt nem: a keret pont azért van, hogy ne kelljen
        munkánként újraszerződni. A TIG-et viszont NEM váltja ki - a keret
        arról szól, milyen feltételekkel dolgozunk együtt, a TIG arról, hogy
        egy konkrét munka elkészült. Ugyanez a szabály az alvállalkozói
        oldalon is (lásd routes/subcontractor_contracts.py)."""
        return self.kell_papir and not self.keret_fedi

    @property
    def szerzodes_rendben(self) -> bool:
        """A szerződés-lépés le van zárva: vagy van papír, vagy keret fedi."""
        return not self.szerzodes_kell or self.szerzodes_kesz

    @property
    def tig_kesz(self) -> bool:
        return papir_kesz(self.tig)

    @property
    def kesz(self) -> bool:
        """Nincs több teendő ezen a projektkódon."""
        return not self.kell_papir or (self.szerzodes_rendben and self.tig_kesz)

    @property
    def alairasra_var(self) -> bool:
        """Kiment, de az aláírt példány még nem jött vissza.

        Csak a KIKÜLDÖTT papírra igaz: a kihagyottnál és a "van már papír"
        esetnél nincs mit visszavárni."""
        return any(
            p is not None and p.allapot == "Kiküldve" and not p.alairt_file_url
            for p in (self.szerzodes, self.tig)
        )


def papir_allas(db: Session, project_code: ProjectCode) -> PapirAllas:
    szerzodes = db.scalars(
        select(MegrendeloiSzerzodes)
        .where(MegrendeloiSzerzodes.project_code_id == project_code.id)
        .order_by(MegrendeloiSzerzodes.id.desc())
    ).first()
    tig = db.scalars(
        select(MegrendeloiTig)
        .where(MegrendeloiTig.project_code_id == project_code.id)
        .order_by(MegrendeloiTig.id.desc())
    ).first()
    return PapirAllas(
        kell_papir=papirt_igenyel(project_code),
        szerzodes=szerzodes,
        tig=tig,
        # A fedettség a projektkód SAJÁT keretszerződés-kötésén múlik, nem
        # azon, hogy az ügyfélnek van-e valahol kerete (lásd
        # models/project_code.keret_fedi).
        keret_fedi=project_code.keret_fedi,
    )


def papir_allasok(db: Session, project_codes: list[ProjectCode]) -> dict[int, PapirAllas]:
    """Ugyanaz, mint a papir_allas(), csak EGYSZERRE sok projektkódra.

    A dashboard teendőlistája minden projektkódot végignéz - soronkénti
    lekérdezéssel az több száz kör lenne minden egyes betöltésnél. Itt két
    lekérdezésből dolgozunk, és a legutóbbi papírt tartjuk meg
    projektkódonként (a papir_allas() is a legnagyobb azonosítójút veszi)."""
    ids = [pk.id for pk in project_codes]
    if not ids:
        return {}

    def legutobbi(modell) -> dict[int, object]:
        sorok = db.scalars(
            select(modell).where(modell.project_code_id.in_(ids)).order_by(modell.id.asc())
        ).all()
        # Növekvő azonosító szerint megyünk, így a későbbi felülírja a korábbit -
        # a végén projektkódonként a LEGUTÓBBI papír marad bent.
        return {p.project_code_id: p for p in sorok}

    szerzodesek = legutobbi(MegrendeloiSzerzodes)
    tigek = legutobbi(MegrendeloiTig)

    # A ráKÖTÖTT keretszerződések, EGY lekérdezésből: enélkül projektkódonként
    # külön kör lenne. Nem az ügyfél keretét nézzük, hanem azt, amit ehhez a
    # kódhoz kötöttek (lásd models/project_code.keret_fedi).
    keret_idk = {pk.contract_id for pk in project_codes if pk.contract_id is not None}
    keretek: dict[int, Contract] = {}
    if keret_idk:
        keretek = {
            c.id: c for c in db.scalars(select(Contract).where(Contract.id.in_(keret_idk)))
        }

    def fedi(pk: ProjectCode) -> bool:
        keret = keretek.get(pk.contract_id) if pk.contract_id is not None else None
        return keret is not None and megrendeloi_keret_ervenyes(keret, pk.datum)

    return {
        pk.id: PapirAllas(
            kell_papir=papirt_igenyel(pk),
            szerzodes=szerzodesek.get(pk.id),
            tig=tigek.get(pk.id),
            keret_fedi=fedi(pk),
        )
        for pk in project_codes
    }
