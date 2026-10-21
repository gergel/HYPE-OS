"""A megrendelői keretszerződések CÉLZOTT áthozatala a Notionból.

Miért van külön szkript, ha a katalógusban ott a "Keretszerződések" lépés?

Mert az a lépés HÁROM forrásból dolgozik (a megrendelői Keretszerződés tábla, az
alvállalkozói keretszerződések, és minden munkatárs saját lapja), és emiatt
végigolvassa a több száz soros "Külsős és belsős" táblát is - a Notion
rate-limitje mellett ez sok perc. Ha csak az a kérdés, hogy "a 28 megrendelői
keretszerződés bent van-e", az fölösleges várakozás, és a napló végén sem
látszik cégenként, mi történt.

Ez a szkript CSAK a megrendelői Keretszerződés táblát nézi, és soronként kiírja,
mi lett vele. Ugyanazt a motort használja, mint a rendes import
(engine.safe_upsert), tehát:

- **idempotens**: újrafuttatva frissít, nem duplikál;
- **nem írja felül a helyi munkát**: amit a HYPE OS-ben módosítottak az előző
  import óta, azt érintetlenül hagyja (lásd notion_import/engine.py);
- **a fájlokat átemeli** az R2-re, mert a Notion fájl-linkjei kb. egy óra alatt
  lejárnak - a Notion URL-t beírni annyi lenne, mint holnapra döglött linkeket
  hagyni;
- **beköti a keret alá tartozó projektkódokat** a keretszerződés felőli
  relationből (`HYPE ADMIN projektkódok`) - a projektkódok saját importja ezt
  nem tudta megtenni, mert ő fut előbb (lásd kosd_a_keret_projektkodjait).

Használat (Railway-en, `railway ssh` után, ahol a NOTION_API_KEY és a
DATABASE_URL már be van állítva):

    python scripts/megrendeloi_keretek_atmentese.py            # áthozatal
    python scripts/megrendeloi_keretek_atmentese.py --proba    # csak megmutatja, mit tenne
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.contract import Contract, ContractType
from app.models.notion_import import NotionImportMap
from app.notion_import import database_ids as db_ids, files
from app.notion_import.client import NotionClient, as_date, extract_properties
from app.notion_import.engine import ImportResult, safe_upsert
from app.notion_import.importers import (
    _szoveg_mezo,
    kosd_a_keret_projektkodjait,
    resolve_client_via_contact,
)
from app.services import document_storage
from app.services.megrendeloi_papir_atvetel import kosd_ugyfelhez_a_kereteket


def _mezok(props: dict, db) -> dict:
    """A Notion sor -> Contract mezők.

    A mezőnevek a MEGRENDELŐI tábláé ("Képviselő", "Nyilvántartásiszám"), az
    alvállalkozói oldal nevei tartalékként - lásd
    notion_import/importers.import_contracts."""
    return {
        "tipus": ContractType.KERETSZERZODES,
        "client_id": resolve_client_via_contact(db, props.get("Akivel szerződünk") or []),
        "ceg_neve": _szoveg_mezo(props, "Cég neve", "Name"),
        "szekhely": _szoveg_mezo(props, "Székhely"),
        "adoszam": _szoveg_mezo(props, "Adószám"),
        "megbizas_targya": _szoveg_mezo(props, "Megbízás tárgya"),
        "szerzodes_allapota": _szoveg_mezo(props, "Keretszerződés állapota"),
        "keltezes": as_date(props.get("Keltezés")),
        "email": _szoveg_mezo(props, "Email"),
        "nev": _szoveg_mezo(props, "Name"),
        "vallalkozas_kepviseloje": _szoveg_mezo(props, "Képviselő", "Vállalkozás képviselője"),
        "vallalkozas_nyilvantartasi_szam": _szoveg_mezo(
            props, "Nyilvántartásiszám", "Nyilvántartási szám", "Vállalkozás nyilvántartási szám"
        ),
        "szerzodes_megjegyzes": _szoveg_mezo(props, "Szerződés megjegyzés", "Megjegyzés"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Megrendelői keretszerződések áthozatala a Notionból.")
    parser.add_argument("--proba", action="store_true", help="Csak megmutatja, mit tenne - nem ír.")
    args = parser.parse_args()

    db = SessionLocal()
    notion = NotionClient()
    result = ImportResult(entity_type="Megrendelői keretszerződés")
    projektkod_osszesen = 0

    darab_elotte = len(
        db.scalars(select(Contract.id).where(Contract.tipus == ContractType.KERETSZERZODES)).all()
    )
    print(f"Most {darab_elotte} megrendelői keretszerződés van az adatbázisban.\n")

    if not document_storage.is_configured():
        print(
            "FIGYELEM: az R2 tárhely nincs beállítva, ezért a fájlok NEM emelhetők át.\n"
            "          A Notion fájl-linkjei kb. egy óra alatt lejárnak, tehát a\n"
            "          szerződés-linkek holnapra használhatatlanok lennének.\n"
            "          Állítsd be az R2_* változókat, és futtasd újra.\n"
        )

    try:
        oldalak = list(notion.query_database(db_ids.KERETSZERZODES))
        print(f"A Notionban {len(oldalak)} sor van.\n")

        for page in oldalak:
            props = extract_properties(page, notion)
            nev = _szoveg_mezo(props, "Cég neve", "Name") or page["id"]

            if args.proba:
                mezok = _mezok(props, db)
                fajl_db = len([u for u in (props.get("Szerződés") or []) if isinstance(u, str)])
                print(
                    f"  {nev[:45]:<45} kepv={'✓' if mezok['vallalkozas_kepviseloje'] else '·'} "
                    f"nyilv={'✓' if mezok['vallalkozas_nyilvantartasi_szam'] else '·'} "
                    f"ugyfel={'✓' if mezok['client_id'] else '·'} fájl={fajl_db} "
                    f"projekt={len(props.get('HYPE ADMIN projektkódok') or [])}"
                )
                continue

            # Az ÁRVA leképezés (a rekordot törölték, a leképezés maradt) ezt a
            # sort korábban véglegesen kizárta az importból. A motor ma már
            # felismeri és újrahasznosítja - itt csak jelezzük, ha ilyet találunk,
            # hogy a naplóból kiderüljön, miért nem volt eddig bent.
            leképezes = db.scalar(
                select(NotionImportMap).where(NotionImportMap.notion_page_id == page["id"])
            )
            arva = leképezes is not None and db.get(Contract, leképezes.entity_id) is None

            szerzodes = safe_upsert(
                db, result, Contract, "Contract", page["id"], _mezok(props, db), label=f"Keretszerződés '{nev}'"
            )
            if szerzodes is None:
                print(f"  ✗ {nev[:45]:<45} KIMARADT (lásd a hibát a végén)")
                continue

            ujak = files.atemel_mindent(db, props, entity_type="contract", entity_id=szerzodes.id, result=result)
            uj_url = files.elso(ujak, "Szerződés")
            if uj_url:
                szerzodes.szerzodes_file_url = uj_url
            # A keret ALÁ TARTOZÓ projektek bekötése - a Notionban a
            # keretszerződés felől is meg van adva a kapcsolat.
            bekotott = kosd_a_keret_projektkodjait(
                db, szerzodes.id, props.get("HYPE ADMIN projektkódok") or []
            )
            projektkod_osszesen += bekotott
            db.commit()

            hivatkozott = len(props.get("HYPE ADMIN projektkódok") or [])
            jelzes = "↻ árva leképezés helyreállítva" if arva else "✓"
            print(
                f"  {jelzes} {nev[:43]:<43} "
                f"kepv={'✓' if szerzodes.vallalkozas_kepviseloje else '·'} "
                f"nyilv={'✓' if szerzodes.vallalkozas_nyilvantartasi_szam else '·'} "
                f"ugyfel={'✓' if szerzodes.client_id else '·'} "
                f"fájl={'✓' if szerzodes.szerzodes_file_url else '·'} "
                f"projekt={bekotott}/{hivatkozott}"
            )
    finally:
        notion.close()

    if args.proba:
        print("\n(Próba mód - semmit nem írtunk.)")
        return 0

    # Akinél a Notionban üres az "Akivel szerződünk", annak a projektkódjai
    # felől még bekötheto az ügyfél.
    kotve = kosd_ugyfelhez_a_kereteket(db)
    db.commit()

    darab_utana = len(
        db.scalars(select(Contract.id).where(Contract.tipus == ContractType.KERETSZERZODES)).all()
    )
    print(f"\n{result}")
    if projektkod_osszesen:
        print(f"{projektkod_osszesen} projektkód bekötve a keretszerződéséhez.")
    if kotve:
        print(f"{kotve} keretszerződés kapott ügyfelet a projektkódjai felől.")
    print(f"Most {darab_utana} megrendelői keretszerződés van az adatbázisban (előtte {darab_elotte}).")
    if result.errors:
        print("\nHIBÁK:")
        for hiba in result.errors:
            print("  -", hiba)
    if result.file_errors:
        print("\nFÁJL-HIBÁK:")
        for hiba in result.file_errors[:20]:
            print("  -", hiba)
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
