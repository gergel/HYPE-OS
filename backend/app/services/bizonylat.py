"""VAN-E SZÁMLA a tétel mögött - egy szabály, egy helyen.

Két külön kérdés, amit könnyű összekeverni:

- **kifizettük-e** (van fizetési dátum, van fizetési mód) - erről a
  services/fizetesi_mod.py szól;
- **van-e róla számla** - erről ez a modul.

A kettő nem ugyanaz, és épp a különbség a lényeg: egy készpénzben kifizetett
tétel, ami mögött nincs számla, a könyvelésben nem elszámolható költség.
A Pénzügyek kassza-kártyája ezért mutatja külön a kettőt (lásd
routes/finance.py `_kassza`).

MI SZÁMÍT SZÁMLÁNAK? Egy tényleges BIZONYLAT, nem egy szándék:

1. a rendszerbe **feltöltött** számla-fájl (`DocumentAttachment`,
   `kategoria="szamla"`) - ez az élő út, ebből áll össze a havi könyvelési
   csomag is (lásd routes/finance.py szamlak_zip);
2. a Notionből örökölt **"Számla pdf"** mező (`Expense.szamla_pdf_urls`) - a
   régi sorokon a fájl ott van, csak nem csatolmányként.

A `szamla` SZÖVEGES mező (a Notion "Számla" property-je) SZÁNDÉKOSAN nem
számít: abban a valóságban számlaszám, "igen", "nincs" és üres string egyaránt
előfordul, tehát a jelenléte nem bizonyítja, hogy a bizonylat megvan.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_attachment import DocumentAttachment


def szamlas_kiadas_ids(db: Session) -> set[int]:
    """Azoknak a KIADÁSOKNAK az azonosítói, amikhez fel van töltve számla.

    Egy lekérdezés, halmazba gyűjtve: soronként kérdezni ugyanezt N+1
    lekérdezést jelentene egy olyan nézetben, ami amúgy is több száz soron fut
    végig."""
    sorok = db.scalars(
        select(DocumentAttachment.entity_id).where(
            DocumentAttachment.entity_type == "expense",
            DocumentAttachment.kategoria == "szamla",
        )
    ).all()
    return {int(x) for x in sorok}


def _van_fajl(ertek: Any) -> bool:
    """Van-e ténylegesen fájl a Notionből örökölt mezőben.

    Az üres lista és az üres dict NEM fájl: a JSON oszlop `[]`-t is tárolhat,
    és az `is not None` ezt még "van"-nak látná."""
    if ertek is None:
        return False
    if isinstance(ertek, (list, dict)):
        return len(ertek) > 0
    return bool(str(ertek).strip())


def van_szamla(kiadas, szamlas_ids: set[int] | None = None) -> bool:
    """Van-e SZÁMLA e mögött a kiadás mögött (lásd a modul leírását)."""
    if szamlas_ids is not None and kiadas.id in szamlas_ids:
        return True
    return _van_fajl(getattr(kiadas, "szamla_pdf_urls", None))
