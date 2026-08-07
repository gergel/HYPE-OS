from datetime import date, datetime

from pydantic import BaseModel, computed_field

from app.models.contract import ContractType

JsonScalar = dict | list | float | str | bool | None


class ContractBase(BaseModel):
    tipus: ContractType
    client_id: int | None = None
    employee_id: int | None = None
    project_id: int | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    megbizas_targya: str | None = None
    szerzodes_allapota: str | None = None
    keltezes: date | None = None
    alairva: bool = False
    # Álló keretszerződés (True) vagy eseti megbízási szerződés (False) -
    # lásd models/contract.py Contract.keretszerzodes.
    keretszerzodes: bool = False
    #: Él-e a keretszerződés (kézi kapcsoló). Eseti szerződéseknél nincs
    #: jelentősége.
    aktiv: bool = True
    netto_osszeg: float | None = None
    teljesites_kezdete: date | None = None
    teljesites_vege: date | None = None
    plusz_afa: bool | None = None


class ContractPeriodBase(BaseModel):
    """Egy keretszerződés érvényességi időszaka. A nyitott vég ("azóta is
    él") és a nyitott kezdet ("a kezdetektől") egyaránt megengedett."""

    kezdet: date | None = None
    veg: date | None = None
    megjegyzes: str | None = None


class ContractPeriodCreate(ContractPeriodBase):
    pass


class ContractPeriodRead(ContractPeriodBase):
    id: int
    contract_id: int

    model_config = {"from_attributes": True}


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    szerzodes_allapota: str | None = None
    #: A keretszerződés be-/kikapcsolása (lásd models/contract.py Contract.aktiv).
    aktiv: bool | None = None
    alairva: bool | None = None
    szerzodes_file_url: str | None = None
    netto_osszeg: float | None = None
    teljesites_kezdete: date | None = None
    teljesites_vege: date | None = None
    plusz_afa: bool | None = None


class ContractRead(ContractBase):
    id: int
    szerzodes_file_url: str | None = None
    #: Mettől meddig élt a keretszerződés - üres lista = időbeli korlát nélkül.
    idoszakok: list[ContractPeriodRead] = []

    # a 'Keretszerződés' / 'Alvállakozó keretszerződés' Notion táblák maradék mezői
    letrehozta_notion: JsonScalar = None
    vallalkozas_kepviseloje: str | None = None
    created_at_notion: datetime | None = None
    keretszerzodes_kuld: bool | None = None
    email: str | None = None
    szemely_notion_ids: JsonScalar = None
    nev: str | None = None
    kulsos_notion_ids: JsonScalar = None
    vallalkozas_nyilvantartasi_szam: str | None = None
    szerzodes_megjegyzes: str | None = None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def brutto_osszeg(self) -> float | None:
        """ÁFA-val növelt összeg - ha a megbízottnak plusz ÁFA-t kell
        felszámolni, a nettó összeg 1,27-szerese, egyébként megegyezik vele."""
        if self.netto_osszeg is None:
            return None
        return round(self.netto_osszeg * 1.27, 2) if self.plusz_afa else self.netto_osszeg
