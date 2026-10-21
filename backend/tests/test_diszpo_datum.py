"""A diszpó levelében / PDF-jében a forgatás dátumánál CSAK a dátum áll, óra
és perc nélkül (a felhasználó kérése, 2026-10). Adatbázis nélküli teszt."""

from datetime import date, time

from app.models.project import Project
from app.services.dispo import _format_hu_date_range


def test_csak_datum_ido_nelkul():
    p = Project(nev="Forgatás (demó)", forgatas_datuma=date(2026, 7, 6),
                forgatas_kezdes_ido=time(8, 0), forgatas_veg_ido=time(17, 30))
    assert _format_hu_date_range(p) == "2026.07.06"
    p.forgatas_datuma_vege = date(2026, 7, 8)
    assert _format_hu_date_range(p) == "2026.07.06 – 2026.07.08"


def test_datum_nelkul_ures():
    assert _format_hu_date_range(Project(nev="Forgatás (demó)")) == ""
