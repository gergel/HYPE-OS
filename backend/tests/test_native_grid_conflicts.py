"""Atomic batch edits reject stale content and changed axes."""
import importlib.util
import sys
from pathlib import Path
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.database import Base
from app.models.employee import Employee
from app.models.diszpo_tabla import DiszpoMunkalap, DiszpoSor, DiszpoOszlop, DiszpoCella

spec = importlib.util.spec_from_file_location("native_grid_routes", Path(__file__).parents[1] / "app/api/routes/diszpo_tabla.py")
grid = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = grid
spec.loader.exec_module(grid)

@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Employee.__table__, DiszpoMunkalap.__table__, DiszpoSor.__table__, DiszpoOszlop.__table__, DiszpoCella.__table__])
    monkeypatch.setattr(grid.munkanap_szamlalo, "urits_gyorsitotar", lambda db: None)
    with Session(engine) as db:
        db.add(DiszpoMunkalap(id=1, nev="Test", sorrend=0, sor_szam=2, oszlop_szam=2, fejlec_sorok=0))
        db.add_all([DiszpoSor(munkalap_id=1, idx=0), DiszpoSor(munkalap_id=1, idx=1), DiszpoOszlop(munkalap_id=1, idx=0), DiszpoOszlop(munkalap_id=1, idx=1)])
        db.add(DiszpoCella(munkalap_id=1, sor_idx=0, oszlop_idx=0, ertek="old", szin="zold"))
        db.commit()
        yield db
    engine.dispose()

def change(**kwargs):
    return grid.CellaIn(sor_idx=0, oszlop_idx=0, ertek="new", ertek_valtozik=True, check_previous=True, **kwargs)

def test_stale_cell_is_not_overwritten(db):
    with pytest.raises(HTTPException) as error:
        grid.set_cellak(1, grid.CellakIn(cellak=[change(expected_ertek="outdated", expected_szin="zold")]), db, None)
    assert error.value.status_code == 409
    db.rollback()
    assert db.scalar(select(DiszpoCella)).ertek == "old"

def test_valid_edit_preserves_color(db):
    grid.set_cellak(1, grid.CellakIn(cellak=[change(expected_ertek="old", expected_szin="zold")]), db, None)
    cell = db.scalar(select(DiszpoCella))
    assert (cell.ertek, cell.szin) == ("new", "zold")

def test_changed_structure_rejected(db):
    before = grid.get_munkalap(1, db, None)
    db.scalar(select(DiszpoOszlop)).cimke = "Renamed"
    db.commit()
    with pytest.raises(HTTPException) as error:
        grid.set_cellak(1, grid.CellakIn(cellak=[change(expected_ertek="old", expected_szin="zold")], expected_rows=before.sorok, expected_columns=before.oszlopok), db, None)
    assert error.value.status_code == 409

def test_conflict_rolls_back_entire_batch(db):
    first = grid.CellaIn(sor_idx=1, oszlop_idx=1, ertek="first", ertek_valtozik=True)
    with pytest.raises(HTTPException):
        grid.set_cellak(1, grid.CellakIn(cellak=[first, change(expected_ertek="wrong")]), db, None)
    db.rollback()
    assert len(list(db.scalars(select(DiszpoCella)))) == 1

def test_duplicate_addresses_rejected(db):
    item = change(expected_ertek="old", expected_szin="zold")
    with pytest.raises(HTTPException) as error:
        grid.set_cellak(1, grid.CellakIn(cellak=[item, item]), db, None)
    assert error.value.status_code == 400
