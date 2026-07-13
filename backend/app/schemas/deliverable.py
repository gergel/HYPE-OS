from datetime import date, datetime

from pydantic import BaseModel

JsonScalar = dict | list | float | str | bool | None


class DeliverableBase(BaseModel):
    projekt_neve: str
    project_code_id: int | None = None
    project_id: int | None = None
    vago_employee_id: int | None = None
    campaign_id: int | None = None
    aki_felvezette_employee_id: int | None = None
    assigned_to_employee_id: int | None = None
    allapot: str | None = None
    hatarido: date | None = None
    koltseg: float | None = None
    kesz_anyag_url: str | None = None
    nyersanyag_url: str | None = None
    anyag_kikuldve: bool = False


class DeliverableCreate(DeliverableBase):
    pass


class DeliverableUpdate(BaseModel):
    allapot: str | None = None
    vago_employee_id: int | None = None
    assigned_to_employee_id: int | None = None
    kesz_anyag_url: str | None = None
    anyag_kikuldve: bool | None = None


class DeliverableRead(DeliverableBase):
    id: int
    # Ha van hozzá tartozó Média Portál (lásd routes/portal_admin.py
    # create_portal_from_deliverable), a frontend ez alapján dönti el, hogy
    # "Portál létrehozása" gombot vagy a meglévő Portálra mutató linket mutassa.
    portal_id: int | None = None

    # az 'Utómunka' Notion tábla maradék mezői, egyenként (lásd scripts/dump_extra_keys.py)
    tobb_vinyo: bool | None = None
    timesheet_status: str | None = None
    stop_timer: bool | None = None
    completed_notion: bool | None = None
    time_minutes: float | None = None
    jovairva: bool | None = None
    total_time: str | None = None
    anyag_zapierbe: bool | None = None
    updated_at_notion: datetime | None = None
    vinyok: JsonScalar = None
    projektkod_szoveg: str | None = None
    completed_time: date | None = None
    vagas_leiras: str | None = None
    aki_felvezette_az_utomunkat_notion_ids: JsonScalar = None
    jovairando_pont: float | None = None
    timesheet_public_notion_ids: JsonScalar = None
    timesheet_private_notion_ids: JsonScalar = None
    forgatas_datuma_notion: str | None = None
    esemeny_neve: str | None = None
    aki_ellenorzesbe_tette_notion_ids: JsonScalar = None
    megrendeloi_email_cimek: str | None = None
    email_megnevezes: str | None = None
    megrendeloi_kontaktok_notion_ids: JsonScalar = None
    archivalas: str | None = None
    label: str | None = None
    assigned_to_notion: JsonScalar = None
    visszajelzessek_notion_ids: JsonScalar = None
    files_vagashoz_urls: JsonScalar = None
    esedekes: str | None = None
    email_forgatas_datum: str | None = None
    xp: str | None = None
    pontozas: float | None = None
    egyeb_megjegyzes: str | None = None
    nyersanyag_felhasznalhatosaga: float | None = None
    technikai_helyesseg: float | None = None
    kreativ_es_kepi_vilag: float | None = None

    model_config = {"from_attributes": True}
