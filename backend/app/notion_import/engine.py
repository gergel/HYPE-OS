"""Generikus, idempotens import-motor: minden importer ezt használja a Notion page ->
HYPE OS rekord létrehozásához/frissítéséhez, és a Notion relation mezők (page ID lista)
a mi FK-jainkra való feloldásához a NotionImportMap táblán keresztül.

Öt éves, élesben használt Notion adat garantáltan tartalmaz olyan sorokat, amik
megsértik a mi szigorúbb sémánk valamelyik megszorítását (pl. két employee ugyanazzal
az e-mail-lel). Ezért minden egyes rekord upsertje saját SAVEPOINT-ban fut: ha egy sor
hibás, csak az a sor esik ki (a result.errors-ba kerül a konkrét okkal), a többi attól
még bekerül."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notion_import import NotionImportMap


@dataclass
class ImportResult:
    entity_type: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    # A Notionból átemelt fájlok száma és a kimaradt fájlok okai. Külön a
    # sor-hibáktól: egy le nem tölthető csatolmány nem hibás rekord, a sor
    # attól még rendben bekerült - csak a fájlja nem jött vele.
    files_copied: int = 0
    file_errors: list[str] = field(default_factory=list)
    # Hány mezőt hagyott érintetlenül az import, mert azt a HYPE OS-ben
    # módosították az előző import óta (lásd _helyben_modositott). Ez NEM hiba:
    # pontosan ez a védelem a lényege.
    protected_fields: int = 0
    protected_rows: int = 0
    # Utólag bekötött kapcsolatok száma (pl. a keretszerződés alá tartozó
    # projektkódok). Ez sem hiba, de a naplóból látszania kell, mert egy
    # ismételt futásnál épp az a jó jel, ha már nulla.
    bekotott_kapcsolatok: int = 0
    # ÖSSZEVETÉS a Notionnal: hány KÉSZ papírt látott a forrásban, és ebből
    # hányat nem sikerült ideköti. A kettő különbsége az, ami miatt a rendszer
    # még mindig hiányzónak mutat egy papírt, ami a Notionban megvan - ezért
    # kell külön számolni, nem elveszni a "kihagyva" összegben.
    notion_kesz_tig: int = 0
    hianyzo_kesz_tig: int = 0

    def __str__(self) -> str:
        summary = f"{self.entity_type}: {self.created} új, {self.updated} frissítve, {self.skipped} kihagyva"
        if self.protected_fields:
            summary += (
                f", {self.protected_fields} mező védve {self.protected_rows} rekordon (helyben módosították)"
            )
        if self.files_copied:
            summary += f", {self.files_copied} fájl átemelve"
        if self.bekotott_kapcsolatok:
            summary += f", {self.bekotott_kapcsolatok} kapcsolat bekötve"
        if self.notion_kesz_tig or self.hianyzo_kesz_tig:
            summary += (
                f"; Notionban kész TIG: {self.notion_kesz_tig + self.hianyzo_kesz_tig}, "
                f"ebből ide nem köthető: {self.hianyzo_kesz_tig}"
            )
        if self.errors:
            summary += f", {len(self.errors)} hiba"
        if self.file_errors:
            summary += f", {len(self.file_errors)} fájl kimaradt"
        return summary

    def error_report(self) -> str:
        lines = [f"  [{self.entity_type}] {msg}" for msg in self.errors]
        lines += [f"  [{self.entity_type}] {msg}" for msg in self.file_errors]
        return "\n".join(lines)


def resolve_relation_ids(db: Session, entity_type: str, notion_page_ids: list[str]) -> list[int]:
    """Notion relation (page ID lista) -> a mi entitásaink integer ID-i. Azokat a
    kapcsolatokat, amiknek a célja még nincs importálva, csendben kihagyja."""
    if not notion_page_ids:
        return []
    rows = db.scalars(
        select(NotionImportMap).where(
            NotionImportMap.entity_type == entity_type,
            NotionImportMap.notion_page_id.in_(notion_page_ids),
        )
    ).all()
    return [r.entity_id for r in rows]


def resolve_relation_id(db: Session, entity_type: str, notion_page_ids: list[str]) -> int | None:
    ids = resolve_relation_ids(db, entity_type, notion_page_ids)
    return ids[0] if ids else None


def _eltavolitott_mezok_nelkul(db: Session, model: type, fields: dict[str, Any]) -> dict[str, Any]:
    """Kihagyja azokat a mezőket, amiket admin eltávolított a rendszerből (lásd
    services/entity_fields.py). Enélkül egy újabb Notion-import visszatöltené
    pont azt az adatot, amit a felhasználó szándékosan kitörölt - az importált
    mezőkészletből ugyanis sok itt már nem kell."""
    from app.services.entity_fields import hidden_fields
    from app.services.entity_registry import ENTITY_MODELS

    # A modellből visszakeressük az entitás kulcsát: az importerek saját,
    # nagybetűs neveket használnak ("Employee"), a mezőkezelés viszont az API
    # kulcsait ("employee") - a modell a közös, biztos kapocs.
    entity_key = next((key for key, m in ENTITY_MODELS.items() if m is model), None)
    if entity_key is None:
        return fields
    eltavolitott = hidden_fields(db, entity_key)
    if not eltavolitott:
        return fields
    return {k: v for k, v in fields.items() if k not in eltavolitott}


def _ertek_kulcs(value: Any) -> str:
    """Egy mezőérték stabil, szöveges lenyomata - ezt hasonlítjuk össze.

    Azért szöveg, és nem a nyers érték, mert ugyanaz az adat sokféle típusban
    fordul meg ugyanazon az úton: a Notionból str/int jön, az adatbázisból
    Decimal/date/Enum jöhet vissza, és egy `Decimal("1000.00") != 1000`
    összehasonlítás tévesen "helyben módosítottnak" mutatna egy változatlan
    mezőt - onnantól pedig az import soha többé nem frissítené."""
    if value is None:
        return ""
    if isinstance(value, Enum):
        return _ertek_kulcs(value.value)
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        # A jelentéktelen záró nullák nélkül: 1000.00 és 1000 ugyanaz az összeg.
        return format(value.normalize(), "f")
    if isinstance(value, float):
        return _ertek_kulcs(Decimal(str(value)))
    if isinstance(value, (list, tuple, set)):
        return "|".join(sorted(_ertek_kulcs(v) for v in value))
    # ORM objektum (pl. relation) - az azonosítója a stabil lenyomat.
    azonosito = getattr(value, "id", None)
    if azonosito is not None and not isinstance(value, (str, int)):
        return f"#{azonosito}"
    return str(value).strip()


def _felulirhato() -> bool:
    """NOTION_IMPORT_OVERWRITE=1 mellett az import a RÉGI módon fut: mindent
    felülír a Notion tartalmával, a helyi módosításokat is.

    Vészkijárat, nem alapértelmezés - akkor kell, ha egy elrontott helyi
    szerkesztést szándékosan a Notion állapotára akarunk visszaállítani."""
    return os.environ.get("NOTION_IMPORT_OVERWRITE", "0").strip().lower() in ("1", "true", "yes")


def _helyben_modositott(obj: Any, key: str, baseline: dict[str, str] | None) -> bool:
    """Hozzányúltak-e ehhez a mezőhöz a HYPE OS-ben az utolsó import óta?

    A `baseline` azt tartja nyilván, mit írt bele LEGUTÓBB az import. Ha a
    mostani adatbázis-érték ezzel egyezik, azóta senki nem módosította -
    ilyenkor a Notion frissítése nyugodtan felülírhatja. Ha eltér, akkor itt
    dolgoztak rajta, és az import nem nyúl hozzá.

    Ha nincs baseline (a rekord még a védelem bevezetése előtt jött be, vagy
    szintetikus kulccsal készült), a KITÖLTÖTT mezőt tekintjük védendőnek, az
    üreset pedig szabadon kitölthetőnek: üres mezőből nem veszhet el munka,
    egy kitöltöttből viszont igen."""
    jelenlegi = _ertek_kulcs(getattr(obj, key, None))
    if baseline is None or key not in baseline:
        return jelenlegi != ""
    return jelenlegi != baseline[key]


def upsert(
    db: Session, model: type, entity_type: str, notion_page_id: str, fields: dict[str, Any]
) -> tuple[Any, bool, list[str]]:
    """Létrehoz vagy frissít egy rekordot a notion_page_id alapján - ez teszi idempotenssé
    az importot (újrafuttatásnál nem duplikál). (rekord, is_new, védett_mezők) hármast ad
    vissza.

    FRISSÍTÉSKOR nem ír felül mindent: azokat a mezőket, amiket az előző import óta a
    HYPE OS-ben módosítottak, érintetlenül hagyja (lásd _helyben_modositott). Enélkül egy
    újrafuttatott import visszaírná a Notion elavult adatát arra, amit itt már befejeztek -
    például egy itt megírt és kiküldött TIG-re vagy egy lezárt utókövetésre.

    Nincs benne hibakezelés - importeren belül a safe_upsert()-öt használd, hacsak nem
    vagy biztos benne, hogy a hívó már véd egy savepoint-tal (lásd get_or_create_unknown_client)."""
    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == notion_page_id))
    fields = _eltavolitott_mezok_nelkul(db, model, fields)

    obj = db.get(model, mapping.entity_id) if mapping else None
    if mapping is not None and obj is None:
        # ÁRVA LEKÉPEZÉS: a leképezés megvan, a rekord viszont már nincs (kézzel
        # törölték, vagy egy tábla ürítése vitte el). Ilyenkor a leképezést
        # ÚJRAHASZNOSÍTJUK, és a rekordot újra létrehozzuk.
        #
        # Enélkül ez a sor VÉGLEG kiesett az importból: a régi kód a hiányzó
        # objektumra hívott setattr()-t, ami AttributeError-ral elszállt, a
        # safe_upsert pedig kihagyta a sort - minden további futásnál újra. Egy
        # egyszer törölt rekordot tehát nem lehetett visszaimportálni, és a
        # napló is csak egy rejtélyes AttributeError-t mutatott.
        db.delete(mapping)
        db.flush()
        mapping = None

    if mapping:
        baseline = mapping.imported_fields if isinstance(mapping.imported_fields, dict) else None
        uj_baseline = dict(baseline or {})
        vedett: list[str] = []
        for key, value in fields.items():
            if not _felulirhato() and _helyben_modositott(obj, key, baseline):
                vedett.append(key)
                continue
            setattr(obj, key, value)
            # A baseline CSAK arra a mezőre frissül, amit tényleg beírtunk - a
            # védett mezőknél megmarad a régi referenciapont, különben a
            # következő futás már nem ismerné fel a helyi módosítást.
            uj_baseline[key] = _ertek_kulcs(value)
        mapping.imported_fields = uj_baseline
        mapping.last_imported_at = datetime.now(timezone.utc)
        db.flush()
        return obj, False, vedett

    obj = model(**fields)
    db.add(obj)
    db.flush()  # kell az obj.id-hoz, mielőtt a mapping sort felvesszük
    db.add(
        NotionImportMap(
            notion_page_id=notion_page_id,
            entity_type=entity_type,
            entity_id=obj.id,
            imported_fields={key: _ertek_kulcs(value) for key, value in fields.items()},
            last_imported_at=datetime.now(timezone.utc),
        )
    )
    db.flush()
    return obj, True, []


def safe_upsert(
    db: Session,
    result: ImportResult,
    model: type,
    entity_type: str,
    notion_page_id: str,
    fields: dict[str, Any],
    label: str,
) -> Any | None:
    """upsert() SAVEPOINT-tal védve: ha ez az egy sor hibázik (pl. UNIQUE ütközés egy
    duplikált e-mailen/sorozatszámon), csak ez a sor esik ki - a result.errors-ba kerül
    a konkrét hibaüzenet és a `label` (hogy a Notion-ban vissza lehessen keresni), a
    tranzakció a savepointig visszagörgetve folytatódik. None-t ad vissza hiba esetén,
    az importer ilyenkor `continue`-zzon a ciklusban."""
    try:
        with db.begin_nested():
            obj, created, vedett = upsert(db, model, entity_type, notion_page_id, fields)
        if created:
            result.created += 1
        else:
            result.updated += 1
        if vedett:
            result.protected_fields += len(vedett)
            result.protected_rows += 1
        return obj
    except Exception as exc:  # noqa: BLE001 - soronkénti izoláció, szándékosan széles
        result.errors.append(f"{label} (notion_page_id={notion_page_id}): {type(exc).__name__}: {exc}")
        return None


def run_importer(name: str, db: Session, fn, *args, **kwargs) -> ImportResult:
    """Egy importer futtatása izolálva, saját tranzakcióval - ha maga az importer
    (nem egy adott sor, hanem a séma feldolgozó kód) hibára fut, rollback-elünk és a
    többi importer attól még lefut a következő (tiszta) tranzakcióban."""
    try:
        result = fn(*args, **kwargs)
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001 - szándékosan széles, hogy egy hibás importer ne állítsa meg a többit
        db.rollback()
        result = ImportResult(entity_type=name)
        result.errors.append(f"importer szintű hiba: {type(exc).__name__}: {exc}")
        return result
