from datetime import date

from pydantic import BaseModel

JsonScalar = dict | list | float | str | bool | None


class ExpenseBase(BaseModel):
    megnevezes: str
    project_code_id: int | None = None
    employee_id: int | None = None
    tipus: str | None = None
    netto: float | None = None
    brutto: float | None = None
    penznem: str = "HUF"
    kifizetes_modja: str | None = None
    fizetes_hatarideje: date | None = None
    kesz: bool = False
    #: Devizás felvezetés: a `penznem`-ben megadott összeget a szerver váltja át
    #: forintra az `arfolyam`-mal, és a `netto`/`brutto` mezőbe már a forint
    #: kerül (lásd services/penznem.py). Forintnál mindkettő elhagyható.
    arfolyam: float | None = None


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    kesz: bool | None = None
    kifizetes_modja: str | None = None
    fizetes_hatarideje: date | None = None
    #: A pénznem újbóli megadása ÚJRASZÁMOLTATJA a forint összeget (lásd
    #: services/penznem.valtsd_at) - ezért csak együtt van értelme az
    #: árfolyammal és az összeggel.
    penznem: str | None = None
    arfolyam: float | None = None
    netto: float | None = None
    brutto: float | None = None


class ExpenseRead(ExpenseBase):
    id: int

    #: MIBŐL lett a forint összeg - devizás felvezetésnél (services/penznem.py).
    eredeti_penznem: str | None = None
    eredeti_netto: float | None = None
    eredeti_brutto: float | None = None

    # a 'Kiadások' / 'Projekt kiadások' / 'Belsős extra kiadások' Notion táblák maradék mezői
    letrehozta_notion: JsonScalar = None
    afa_osszege: float | None = None
    szamla: str | None = None
    kiadas_megnevezese_projekt_kod: str | None = None
    netto_forintban_notion: float | None = None
    fizetes_datuma: date | None = None
    mikor_fizetett: str | None = None
    szamla_pdf_urls: JsonScalar = None
    plusz_afa: str | None = None
    hozzaadas_a_kiadasokhoz: bool | None = None
    forintban_notion: float | None = None
    kiadas_datuma: date | None = None
    projekt_kiadasok_notion_ids: JsonScalar = None
    kiadasok_notion_ids: JsonScalar = None
    szamla_statusza: str | None = None
    fedezes: str | None = None
    osszes_kiadas_notion: float | None = None
    tulora_osszege: float | None = None
    plusz_afa_mezo: str | None = None
    datum_notion: JsonScalar = None
    projektkod_notion: JsonScalar = None
    egyeb_kiadas: JsonScalar = None
    tulora_orabere: float | None = None
    tulora_szama: float | None = None
    egyeni_afa_osszege: float | None = None
    megjegyzes: str | None = None
    plusz_napok_ara: float | None = None
    plusz_napok_szama: float | None = None

    model_config = {"from_attributes": True}


class RevenueBase(BaseModel):
    project_code_id: int
    bevetel_formaja: str | None = None
    #: Beleszámít-e az ÉVES bevételbe (None = igen). Lásd
    #: services/elszamolas.bevetel_beleszamit - a "nem volt tranzakció"
    #: formájú sorok e mező nélkül is kimaradnak.
    beleszamit_a_bevetelekbe: bool | None = None
    netto: float | None = None
    brutto: float | None = None
    penznem: str = "HUF"
    #: HOGYAN jött be a pénz (Készpénz / Átutalás) - ebből számol a kassza,
    #: lásd services/fizetesi_mod.py.
    fizetes_modja: str | None = None
    fizetes_hatarideje: date | None = None
    fizetes_datuma: date | None = None
    szamla_kiallitva_datuma: date | None = None
    #: Devizás felvezetés: a `penznem`-ben megadott összeget a szerver váltja át
    #: forintra az `arfolyam`-mal, és a `netto`/`brutto` mezőbe már a forint
    #: kerül (lásd services/penznem.py). Forintnál mindkettő elhagyható.
    arfolyam: float | None = None


class RevenueCreate(RevenueBase):
    pass


class RevenueUpdate(BaseModel):
    fizetes_datuma: date | None = None
    fizetes_modja: str | None = None
    szamla_kiallitva_datuma: date | None = None
    #: Lásd ExpenseUpdate - a pénznem újbóli megadása újraszámoltat.
    penznem: str | None = None
    arfolyam: float | None = None
    netto: float | None = None
    brutto: float | None = None


class RevenueRead(RevenueBase):
    id: int

    #: MIBŐL lett a forint összeg - devizás felvezetésnél (services/penznem.py).
    eredeti_penznem: str | None = None
    eredeti_netto: float | None = None
    eredeti_brutto: float | None = None

    # A feltöltött KIMENŐ (megrendelői) számla - a havi számla-csomagba is
    # ebből kerül be a kimenő oldal (lásd routes/finance.py szamlak_zip).
    szamla_filename: str | None = None
    szamla_file_url: str | None = None

    nev: str | None = None
    forint_netto_notion: float | None = None
    plusz_afa: str | None = None
    mikor_fizetett: str | None = None
    megjegyzes: str | None = None

    model_config = {"from_attributes": True}


class KpForgalomBase(BaseModel):
    expense_id: int | None = None
    #: Melyik projekthez tartozik - önálló, egyszerű hivatkozás ("Projekt
    #: kiadás"), NEM az expense_id-hoz kötött duplikátum-elkerülés (lásd
    #: models/finance.KpForgalom.project_code_id).
    project_code_id: int | None = None
    #: Az IRÁNY: "bevetel" vagy "kiadas". Importált sornál ez sokszor üres - ott
    #: a Notion "Forintban" formulájának előjele döntött (lásd
    #: models/finance.KpForgalom.forintban). Kézzel szerkesztve viszont EZ a
    #: mérvadó: az összeg vagy az irány átírása félreteszi az importált
    #: formula-értéket (lásd routes/finance._kp_forgalom_kezi_javitas).
    forgalom: str | None = None
    osszeg: float | None = None
    penznem: str = "HUF"
    #: Devizás felvezetés: a `penznem`-ben megadott összeget a szerver váltja
    #: át forintra ezzel (lásd services/penznem.py) - az `osszeg` mezőbe már a
    #: forint kerül. Forintnál elhagyható.
    arfolyam: float | None = None
    #: Van-e mögötte SZÁMLA - kézzel állítható (legördülő: van / nincs), nem a
    #: feltöltött fájlból derül ki (lásd models/finance.KpForgalom.van_szamla).
    van_szamla: bool = False
    legalis: str | None = None
    kiadas_datuma: date | None = None
    megnevezes: str | None = None


class KpForgalomCreate(KpForgalomBase):
    pass


class KpForgalomUpdate(KpForgalomBase):
    pass


class KpForgalomRead(KpForgalomBase):
    id: int

    #: MIBŐL lett a forint összeg - devizás felvezetésnél (services/penznem.py).
    eredeti_penznem: str | None = None
    eredeti_osszeg: float | None = None

    kiadas_sum_notion: float | None = None
    #: A Notion "Forintban" formulájának ELŐJELES értéke - a kiadásokon
    #: negatív. Amíg megvan, EZ dönti el az irányt (lásd
    #: models/finance.KpForgalom.forintban).
    forintban_notion: float | None = None
    #: A sor összege és iránya, ahogy a kassza számol vele - hogy a felületnek
    #: ne kelljen újra levezetnie.
    forintban: float | None = None
    kiadas_e: bool = False
    #: ATM-felvétel: a kasszába érkezik, de se a legális, se a fekete oldalra
    #: nem kerül - és az irányát sem az előjel adja, hanem ez a szabály.
    atvezetes_e: bool = False

    model_config = {"from_attributes": True}


class KifizetesIn(BaseModel):
    """Egy TIG "kifizetve" jelölésének kérése (külsős és belsős egyaránt).

    A `kiadasba_kerul=False` arra való, amikor a pénz TÉNYLEG el lett utalva,
    de a költség NEM ebben a rendszerben van elszámolva - például a bank- vagy
    a könyvelői oldalon már szerepel, és egy itteni Kiadás sor csak
    megkétszerezné a Pénzügy összesítőiben. A papír állapota ilyenkor is
    "kifizetve" lesz (a havi áttekintésben nem marad teendőként), csak nem
    keletkezik hozzá Expense sor.

    Alapértéke True, tehát aki nem küldi a mezőt (régi hívások), annál a
    viselkedés változatlan: keletkezik a Kiadás sor.

    Ha a TIG-hez MÁR tartozik Kiadás sor, azt a False nem szedi ki: egy
    meglévő pénzügyi tételt csak a Pénzügy -> Kiadások alatt lehet törölni -
    onnan viszont igen, és a törlés a papírt is visszadobja "nincs kifizetve"
    állapotba (lásd services/kiadas_kapcsolatok.py).
    """

    kiadasba_kerul: bool = True
    #: MIKOR utaltuk el ténylegesen. Üresen a mai nap - a jelölés viszont
    #: gyakran csak napokkal a tényleges utalás után történik meg, és akkor a
    #: pénzügyi kimutatásban rossz napon állna a tétel. Ide kerül a papír
    #: `utalas_datuma` mezője és a Kiadás sor fizetési dátuma is.
    kifizetes_datuma: date | None = None
