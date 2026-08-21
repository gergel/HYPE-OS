from datetime import date, datetime

from pydantic import BaseModel, Field, computed_field

from app.models.employee import EmployeeType, SystemRole

JsonScalar = dict | list | float | str | bool | None


class EmployeeBase(BaseModel):
    full_name: str
    tipus: EmployeeType
    email: str | None = None
    telefon: str | None = None
    jogositvany: str | None = None
    elso_munkanap: date | None = None
    utolso_munkanap: date | None = None
    #: Belsős napidíj - a projekt önköltségéhez, NEM kiadás-sor (lásd
    #: models/employee.py és services/belsos_koltseg.py).
    napi_dij: float | None = None
    #: Hány napra van szerződve egy hónapban, és mennyi az azon FELÜLI nap
    #: díja. A kettő együtt árazza át a hónap végi forgatásokat (lásd
    #: services/munkanap_szamlalo.py).
    szerzodott_napok: int | None = None
    plusz_nap_napi_dij: float | None = None


class EmployeeCreate(EmployeeBase):
    role: SystemRole = SystemRole.OPERATOR
    #: További szerepkörök az elsődlegesen felül (lásd models/employee.szerepkorei).
    tovabbi_szerepkorok: list[SystemRole] | None = None
    # opcionális - ha nincs megadva, hashed_password=None marad (ugyanúgy,
    # mint a Notionből importált munkatársaknál), az admin később a
    # Beállítások oldalon állíthat be jelszót neki, ha bejelentkezést igényel.
    password: str | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    role: SystemRole | None = None
    tovabbi_szerepkorok: list[SystemRole] | None = None
    tipus: EmployeeType | None = None
    email: str | None = None
    telefon: str | None = None
    jogositvany: str | None = None
    is_active: bool | None = None
    napi_dij: float | None = None
    szerzodott_napok: int | None = None
    plusz_nap_napi_dij: float | None = None


class EmployeeRead(EmployeeBase):
    id: int
    role: SystemRole
    tovabbi_szerepkorok: list[str] | None = None
    is_active: bool
    # a nyers jelszó-hash sosem kerül ki a válaszban (exclude=True) - csak azt
    # a bool jelzőt adjuk vissza, hogy van-e egyáltalán beállítva (lásd
    # Beállítások oldal munkatárs-keresője: alapból csak azokat listázza, akiknek
    # már van hozzáférése).
    hashed_password: str | None = Field(default=None, exclude=True)

    # a 'Külsős és belsős' Notion tábla maradék mezői, egyenként
    technikai_ismeret: str | None = None
    vallalkozas_kepviselo: str | None = None
    leltar_notion_ids: JsonScalar = None
    hany_visszajelzese_van_notion: JsonScalar = None
    first_name: str | None = None
    last_name: str | None = None
    munkanapok_notion: JsonScalar = None
    linkedin_profile: str | None = None
    twitter_profile: str | None = None
    facebook_profile: str | None = None
    photo_url: str | None = None
    kulsos_tig_notion_ids: JsonScalar = None
    belsos_tig_notion_ids: JsonScalar = None
    orabler_notion: str | None = None
    napidij_notion: str | None = None
    extra_kiadas_megnevezes: str | None = None
    extra_kiadas_osszeg: float | None = None
    extra_kiadas_datuma: date | None = None
    belsos_havi_tig: bool | None = None
    source: str | None = None
    events_involved_count_notion: JsonScalar = None
    netto_osszeg: float | None = None
    linked_events_notion_ids: JsonScalar = None
    leltar_hiany_20240415_notion: JsonScalar = None
    legutolso_napi_dij_megegyezes: str | None = None
    milyen_suru_hivjuk: str | None = None
    megbizas_targya: str | None = None
    szallito_notion_ids: JsonScalar = None
    keltezes_datuma: date | None = None
    archive_technika_elhagyas_notion_ids: JsonScalar = None
    nyilvantartasi_szam: str | None = None
    vallakozas_szekhely: str | None = None
    van_e_email_cime_notion: JsonScalar = None
    vallakozas_neve: str | None = None
    phone_2: str | None = None
    megjegyzes: str | None = None
    honnan_ismerjuk: str | None = None
    birthday: date | None = None
    kiadas_projektkodja_notion_ids: JsonScalar = None
    formula_2_notion: JsonScalar = None
    main_database_notion_ids: JsonScalar = None
    vallalkozas_adoszama: str | None = None
    plusz_afa: bool | None = None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def has_password(self) -> bool:
        return bool(self.hashed_password)

    @computed_field
    @property
    def vedett_admin(self) -> bool:
        """VÉDETT RENDSZERGAZDA-e ez a fiók (lásd core/security.py).

        Számolt mező, nem oszlop: a védettség a beállításból következik, tehát
        egy tárolt jelölő csak egy újabb dolog lenne, ami elcsúszhat a
        valóságtól. A felület ebből tudja, hogy ennél a munkatársnál ne
        kínálja fel a kikapcsolást és a jogosultság-korlátozást."""
        # Itt importálunk, nem a fájl tetején: a core.security a modelleket
        # húzza be, a sémák pedig a modelleket - a felső szintű import körkörös
        # lenne.
        from app.core.security import vedett_admin_emailek

        return bool(self.email) and self.email.strip().casefold() in vedett_admin_emailek()


class EmployeeDocumentRead(BaseModel):
    id: int
    employee_id: int
    filename: str
    url: str
    content_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RateBase(BaseModel):
    orabler: float | None = None
    napibler: float | None = None
    tulora: float | None = None
    plusz_nap: float | None = None
    havi_alap: float | None = None
    elso_munkanap: date | None = None
    utolso_munkanap: date | None = None


class RateCreate(RateBase):
    employee_id: int


class RateUpdate(RateBase):
    pass


class RateRead(RateBase):
    id: int
    employee_id: int
    fotos_napi_ber: float | None = None
    nev: str | None = None

    model_config = {"from_attributes": True}
