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


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    kesz: bool | None = None
    kifizetes_modja: str | None = None
    fizetes_hatarideje: date | None = None


class ExpenseRead(ExpenseBase):
    id: int

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
    arfolyam: float | None = None
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
    netto: float | None = None
    brutto: float | None = None
    penznem: str = "HUF"
    fizetes_hatarideje: date | None = None
    fizetes_datuma: date | None = None
    szamla_kiallitva_datuma: date | None = None


class RevenueCreate(RevenueBase):
    pass


class RevenueUpdate(BaseModel):
    fizetes_datuma: date | None = None
    szamla_kiallitva_datuma: date | None = None


class RevenueRead(RevenueBase):
    id: int

    # A feltöltött KIMENŐ (megrendelői) számla - a havi számla-csomagba is
    # ebből kerül be a kimenő oldal (lásd routes/finance.py szamlak_zip).
    szamla_filename: str | None = None
    szamla_file_url: str | None = None

    nev: str | None = None
    forint_netto_notion: float | None = None
    plusz_afa: str | None = None
    mikor_fizetett: str | None = None
    megjegyzes: str | None = None
    arfolyam: float | None = None

    model_config = {"from_attributes": True}


class KpForgalomBase(BaseModel):
    expense_id: int | None = None
    forgalom: str | None = None
    osszeg: float | None = None
    penznem: str = "HUF"
    legalis: str | None = None
    kiadas_datuma: date | None = None


class KpForgalomCreate(KpForgalomBase):
    pass


class KpForgalomUpdate(KpForgalomBase):
    pass


class KpForgalomRead(KpForgalomBase):
    id: int

    kiadas_sum_notion: float | None = None
    forintban_notion: float | None = None
    megnevezes: str | None = None

    model_config = {"from_attributes": True}
