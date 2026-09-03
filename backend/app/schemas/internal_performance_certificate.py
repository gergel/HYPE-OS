from datetime import date, datetime

from pydantic import BaseModel, computed_field

from app.services.hu_datum import honap_neve


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
    #: Melyik saját cégéről számlázza ezt a hónapot (üres = saját nevében).
    vallalkozas_id: int | None = None
    megjegyzes: str | None = None
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    megbizas_targya: str | None = None
    teljesites_datuma: date | None = None
    #: A teljesítés szabad szövegként (a felhasználó kérése) - a felület ezt
    #: kéri be, és a TIG dokumentumra is ez kerül.
    teljesites_szoveg: str | None = None
    keltezes: date | None = None
    fizetesi_hatarido: date | None = None
    utalas_datuma: date | None = None
    file_url: str | None = None
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

    @computed_field
    @property
    def honap_nev(self) -> str:
        """A hónap BETŰVEL - a Belsős TIG sehol nem írja ki számmal."""
        return honap_neve(self.honap)
