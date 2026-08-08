"""A papírra kerülő TÉTEL-SZÖVEG: mit igazol / mire szól ez a dokumentum.

Ha egy szerződés vagy egy TIG több munkát fed - három nap forgatást egy
számlán, vagy két ember munkáját egy fél nevében -, akkor magán a PAPÍRON is
látszania kell, hogy miről szól. Enélkül a dokumentum egyetlen projektkódot
mutatna, és nem derülne ki belőle, mi van benne.

Nem kell hozzá új Google Docs sablon: a meglévő szöveges helyőrzőket
(`targy`, `projkod`, `projektnev`, `tido`) bővítjük ki. Egytételes papírnál -
ez a leggyakoribb eset - MINDEN pontosan úgy néz ki, mint eddig: a felsorolás
csak akkor jelenik meg, ha tényleg van mit felsorolni.

A sortörést szándékosan kerüljük: a Docs API replaceAllText mezője egysoros
szöveget vár, ezért pontosvessző és gondolatjel tagolja a felsorolást."""

from __future__ import annotations

from typing import Protocol


class Tetel(Protocol):
    """Amit egy tételről tudni kell a szöveghez - a ContractTetel és a
    PerformanceCertificateTetel is ilyen."""

    project_id: int
    employee_id: int
    netto_osszeg: float | None
    megnevezes: str | None


def _osszeg(ertek) -> str:
    # float(): a Numeric oszlop az adatbázisból Decimal-ként jön vissza.
    return f"{float(ertek):,.0f}".replace(",", " ") + " Ft"


def _projekt_datum(projekt) -> str:
    if projekt is None or projekt.forgatas_datuma is None:
        return ""
    vege = projekt.forgatas_datuma_vege
    if vege and vege != projekt.forgatas_datuma:
        return f"{projekt.forgatas_datuma.strftime('%Y.%m.%d.')}-{vege.strftime('%Y.%m.%d.')}"
    return projekt.forgatas_datuma.strftime("%Y.%m.%d.")


def tetel_sor(tetel) -> str:
    """Egy tétel egy sorban: dátum, projektkód, ember, és ha tudható, összeg.

    Pl.: "2026.06.01. QASZ-A – Balla Berci – 100 000 Ft" """
    projekt = tetel.project
    reszek: list[str] = []
    datum = _projekt_datum(projekt)
    kod = (projekt.projektkod_szoveg if projekt else None) or (projekt.nev if projekt else None) or ""
    fej = " ".join(x for x in (datum, kod) if x)
    if fej:
        reszek.append(fej)
    if tetel.employee is not None:
        reszek.append(tetel.employee.full_name)
    if tetel.megnevezes:
        reszek.append(tetel.megnevezes)
    if tetel.netto_osszeg is not None:
        reszek.append(_osszeg(tetel.netto_osszeg))
    return " – ".join(reszek)


def felsorolas(tetelek: list) -> str:
    """A tételek egy sorban, pontosvesszővel elválasztva. Üres, ha legfeljebb
    egy tétel van (olyankor nincs mit felsorolni)."""
    if len(tetelek) <= 1:
        return ""
    return "; ".join(sor for sor in (tetel_sor(t) for t in tetelek) if sor)


def targy_szovege(megbizas_targya: str | None, tetelek: list) -> str:
    """A "megbízás tárgya" mező a papíron - több tételnél a felsorolással
    kiegészítve, hogy a dokumentumból kiderüljön, mit fed."""
    alap = (megbizas_targya or "").strip()
    lista = felsorolas(tetelek)
    if not lista:
        return alap
    return f"{alap} ({lista})" if alap else lista


def projektkodok_szovege(tetelek: list, tartalek: str | None = None) -> str:
    """Az összes érintett projektkód, ismétlés nélkül, a tételek sorrendjében."""
    kodok = [
        t.project.projektkod_szoveg
        for t in tetelek
        if t.project is not None and t.project.projektkod_szoveg
    ]
    egyediek = list(dict.fromkeys(kodok))
    return ", ".join(egyediek) if egyediek else (tartalek or "")


def projektnevek_szovege(tetelek: list, tartalek: str | None = None) -> str:
    """Az összes érintett projekt neve, ismétlés nélkül."""
    nevek = [t.project.nev for t in tetelek if t.project is not None and t.project.nev]
    egyediek = list(dict.fromkeys(nevek))
    return ", ".join(egyediek) if egyediek else (tartalek or "")


def teljesites_szovege(sajat_szoveg: str | None, tetelek: list, tartalek: str = "") -> str:
    """A teljesítés ideje a papíron.

    Amit a felhasználó beírt, az az igazság - ő a gazdája. Csak akkor
    egészítjük ki a projektek dátumaiból, ha üresen hagyta ÉS több projektről
    szól a papír: ilyenkor egyetlen nap dátuma félrevezető lenne."""
    sajat = (sajat_szoveg or "").strip()
    if sajat:
        return sajat
    datumok = [
        _projekt_datum(t.project)
        for t in tetelek
        if t.project is not None and _projekt_datum(t.project)
    ]
    egyediek = list(dict.fromkeys(datumok))
    if len(egyediek) > 1:
        return ", ".join(egyediek)
    return egyediek[0] if egyediek else tartalek
