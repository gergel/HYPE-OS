from datetime import date, datetime

from pydantic import BaseModel, computed_field


class PerformanceCertificateInvoiceRead(BaseModel):
    id: int
    filename: str
    url: str
    content_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PerformanceCertificateRead(BaseModel):
    id: int
    project_id: int
    employee_id: int
    allapot: str | None = None
    file_url: str | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    megbizas_targya: str | None = None
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    teljesites_kezdete: date | None = None
    teljesites_vege: date | None = None
    keltezes: date | None = None
    email: str | None = None
    invoices: list[PerformanceCertificateInvoiceRead] = []
    szamla_kifizetve: bool = False
    expense_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def brutto_osszeg(self) -> float | None:
        if self.netto_osszeg is None:
            return None
        return round(self.netto_osszeg * 1.27, 2) if self.plusz_afa else self.netto_osszeg
