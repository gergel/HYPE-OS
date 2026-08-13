from datetime import date

from pydantic import BaseModel


class ProjectCodeBase(BaseModel):
    projektkod: str
    client_id: int
    contract_id: int | None = None
    datum: date | None = None
    esemeny_allapota: str | None = None
    penznem: str = "HUF"
    arfolyam: float | None = None
    tig_statusza: str | None = None
    szamla_statusza: str | None = None
    megjegyzes: str | None = None
    teljesites_datuma: date | None = None
    utalas_datuma: date | None = None
    szamla_url: str | None = None
    tig_alairva_url: str | None = None


class ProjectCodeCreate(ProjectCodeBase):
    pass


class ProjectCodeUpdate(BaseModel):
    esemeny_allapota: str | None = None
    contract_id: int | None = None
    tig_statusza: str | None = None
    szamla_statusza: str | None = None
    megjegyzes: str | None = None
    van_szerzodes: bool | None = None
    papir_nelkul: bool | None = None
    papir_nelkul_indoka: str | None = None


class ProjectCodeRead(ProjectCodeBase):
    id: int
    #: Számított értékek (lásd models/project_code.py) - a lista ezekből
    #: mutatja, hogy jött-e ki a projekt.
    bevetel: float
    osszes_koltseg: float
    becsult_profit: float

    # A papírozás kapcsolói (lásd models/project_code.py): van-e szerződés a
    # projekt mögött, illetve papír nélkül számoljuk-e el.
    van_szerzodes: bool = True
    papir_nelkul: bool = False
    papir_nelkul_indoka: str | None = None

    # a 'HYPE ADMIN projektkódok' Notion tábla maradék mezői, egyenként (lásd
    # app/models/project_code.py) - nem egy közös 'extra' JSON-ban.
    teljesites_datum_formazva: str | None = None
    netto_osszeg: float | None = None
    megrendelo_szekhelye: str | None = None
    profit_szazalek_notion: dict | list | float | str | None = None
    geri_projekt: str | None = None
    szerzodes_targya: str | None = None
    keltezes_datum_formazva: str | None = None
    gyartasi_koltseg_notion: dict | list | float | str | None = None
    szerzodes_specialis_eset: str | None = None
    fizetesi_hatarido: date | None = None
    megrendelo_nyilvantartasi_szam: str | None = None
    szerzodes_kuldes: bool = False
    osszes_koltseg_notion: dict | list | float | str | None = None
    tig_teljesitesi_ido: str | None = None
    megrendelo_neve: str | None = None
    osszesen_netto_notion: dict | list | float | str | None = None
    megrendelo_adoszama: str | None = None
    netto_notion: dict | list | float | str | None = None
    helyszin: str | None = None
    datum_megjegyzes: str | None = None
    szerzodes_plusz_afa: str | None = None
    tig_projektnev: str | None = None
    specialis_eset: str | None = None
    szerzodes_helye: str | None = None
    szerzodes_netto_osszeg: float | None = None
    megrendeloi_emailek: str | None = None
    brutto_notion: dict | list | float | str | None = None
    kulsos_notion_ids: dict | list | float | str | None = None
    alvallalkozok_koltsege_notion: dict | list | float | str | None = None
    darabolva: dict | list | float | str | None = None
    vagasi_koltseg_notion: dict | list | float | str | None = None
    project_nev: str | None = None
    szerzodes_statusza: str | None = None
    plusz_afa: str | None = None
    megerte_e: dict | list | float | str | None = None
    megrendelo_kepviseloje: str | None = None
    szerzodes_projekt_nev: str | None = None
    teljesites: str | None = None
    tig_kikuldve: bool = False
    adminisztracios_tablaban: str | None = None
    tig_specialis: str | None = None
    keltezes_datuma: date | None = None
    lejart_notion: dict | list | float | str | None = None
    megbizas_targya: str | None = None
    belsos_koltseg_akkor: float | None = None
    vallalasi_ar_notion: dict | list | float | str | None = None
    tovabbi_dokumentumok: dict | list | float | str | None = None
    utomunkak_notion: dict | list | float | str | None = None
    bevetel_formaja: str | None = None
    darabolas_notion_ids: dict | list | float | str | None = None
    megrendelo_email: str | None = None
    forintban_notion: dict | list | float | str | None = None
    szerzodes_keltezes_datuma: date | None = None
    belsos_koltseg_notion: dict | list | float | str | None = None
    belso_plusz_koltseg_notion: dict | list | float | str | None = None
    tig_url: str | None = None

    model_config = {"from_attributes": True}
