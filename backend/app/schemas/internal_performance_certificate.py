from datetime import datetime

from pydantic import BaseModel, computed_field


class InternalPerformanceCertificateInvoiceRead(BaseModel):
    id: int
    filename: str
    url: str
    content_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InternalPerformanceCertificateRead(BaseModel):
    id: int
    employee_id: int
    ev: int
    honap: int
    allapot: str | None = None
    megjegyzes: str | None = None
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    invoices: list[InternalPerformanceCertificateInvoiceRead] = []
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
