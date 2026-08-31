"""Generikus CRUD router factory - list/get/create/update/delete végpontokat épít
egy SQLAlchemy modellre és a hozzá tartozó Pydantic sémákra, hogy a 20+ entitáshoz
ne kelljen ugyanazt a boilerplate-et kézzel megismételni minden modulban.
"""

import inspect
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    DEFAULT_WRITE_ROLES,
    Role,
    check_page_action,
    check_tab_action,
    get_current_user,
    require_roles,
)
from app.models.employee import Employee
from app.services import entity_fields, notion_mapping
from app.services.detail_tabs import OTHER_TAB_KEY, get_field_tab_map

# Soha nem PATCH-elhető mezők, még akkor sem, ha valódi oszlopok - a "minden
# adat szerkeszthető" elv alól ez az egyetlen kivétel (biztonsági okból).
_PATCH_DENYLIST = {"id", "hashed_password"}


def _coerce_value(column: Any, value: Any) -> Any:
    """A böngészőből érkező nyers JSON értéket (string/number/bool/null) az
    oszlop tényleges Python típusára alakítja, ahol ez nem triviális (Date/
    DateTime oszlopok stringként érkeznek az inline-szerkesztő inputokból)."""
    if value is None or not isinstance(value, str):
        return value
    py_type = getattr(column.type, "python_type", None)
    if py_type is date:
        return date.fromisoformat(value[:10])
    if py_type is datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    # Egy legördülős cella (pl. EditableStatusBadge) mindig szöveget küld,
    # akkor is, ha a mögötte álló oszlop valójában szám (pl. egy FK-t
    # reprezentáló választó, mint a KP forgalom "Projektkód" mezője).
    if py_type is int:
        return int(value)
    if py_type is float:
        return float(value)
    return value


def build_crud_router(
    *,
    model: type,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    prefix: str,
    tags: list[str],
    page: str,
    write_roles: tuple[Role, ...] = DEFAULT_WRITE_ROLES,
    #: (data, db) -> data, VAGY (data, db, current_user) -> data - a
    #: paraméterszám dönti el, kapja-e a bejelentkezett embert (lásd lent a
    #: create_item-ben; pl. routes/hype_todo.py "Aki felvezette" automatikus
    #: kitöltése). A meglévő kétparaméteres hookok változatlanul működnek.
    before_create: Callable[..., dict] | None = None,
    m2m_fields: dict[str, tuple[str, type]] | None = None,
    list_read_schema: type[BaseModel] | None = None,
    before_update: Callable[[Any, dict, Session, Employee], None] | None = None,
    after_update: Callable[[Any, dict, dict[str, dict[str, set[int]]], Session, Employee], None] | None = None,
    before_delete: Callable[[Any, Session], None] | None = None,
    entity_type: str | None = None,
    list_options: tuple[Any, ...] = (),
    sor_szuro: Callable[[Any, Session, Employee], Any] | None = None,
    #: (sorok, db, current_user) -> sorok - a kimenő JSON-sorok MEZŐNKÉNTI
    #: szűrése a bejelentkezett ember jogai szerint (pl. a projektkód
    #: pénz-mezőinek kitakarása /penzugyek-jog nélkül, lásd
    #: routes/project_codes._penz_kimenet_szuro). A lista, az egyedi GET, a
    #: create és a PATCH válaszára is lefut - listát kap, hogy a jog-lekérdezés
    #: egyszer fusson, ne soronként.
    kimenet_szuro: Callable[[list[dict], Session, Employee], list[dict]] | None = None,
) -> APIRouter:
    """page: a frontend/lib/nav.ts oldal-href-je (pl. "/projektek"), amihez ez az
    entitás tartozik - a Beállítások oldalon egyénenként beállított
    page_permissions (lásd core/security.check_page_action) ez alapján dönti
    el, ki hozhat létre/szerkeszthet/törölhet ezen az entitáson (a durvább
    admin/operator szerepkör-ellenőrzés MELLETT, nem helyette).

    m2m_fields: {payload_key: (relationship_attr_name, related_model)} a many-to-many mezőkhöz
    (pl. Project.crew_employee_ids -> ("crew", Employee)), amiket a sima **data konstruktor nem tud kezelni.

    update_schema: jelenleg nem használja a PATCH végpont ("minden mező helyben
    szerkeszthető" - lásd update_item) - az a nyers JSON body-t fogadja és
    bármelyik valódi oszlopot elfogadja, hogy ne kelljen entitásonként kézzel
    karban tartani egy 50-140 mezős Update sémát. A paraméter a hívási helyeken
    (routes/*.py) marad, hogy ne kelljen mindet átírni, és mert dokumentálja,
    milyen mezőkre gondolt eredetileg az adott entitás Update DTO-ja.

    list_read_schema: ha meg van adva, a lista végpont (GET "") ezt a szűkebb sémát
    használja read_schema helyett - nagyon széles táblákhoz (pl. Project ~140 oszlop),
    ahol a listanézet ténylegesen csak pár mezőt jelenít meg, de a teljes séma
    soronkénti validálása/JSON-ba szerializálása felesleges terhelés minden egyes
    listaoldal-betöltésnél. Az egyedi rekord GET továbbra is a teljes read_schema-t adja.

    before_update: PATCH közben, MÉG A MENTÉS ELŐTT hívódik (obj, data, db,
    current_user) paraméterekkel - itt kell ellenőrizni, hogy a beküldött
    mezők együtt értelmesek-e (pl. a projektkódnál a "papír nélkül"
    jelöléshez kötelező az indok, lásd routes/project_codes.py), vagy hogy
    magának a felhasználónak van-e joga ehhez a konkrét váltáshoz (pl. az
    utómunka csak azt engedi ellenőrzésbe tenni, aki már írt hozzá vágói
    visszajelzést, lásd routes/postproduction.py). Azért nem az after_update
    való erre: az a commit UTÁN fut, tehát az ott dobott hiba már egy
    elmentett állapotra panaszkodna. `obj` még a RÉGI értékeket tartalmazza,
    `data` a beküldött mezőket - a kettőt együtt kell nézni, mert egy PATCH
    tipikusan csak a változó mezőt küldi el.

    after_update: PATCH után hívódik (obj, data, m2m_changes, db, current_user) paraméterekkel,
    miután a rekord már commitolva/refresh-elve van - side effect-ekhez (pl. értesítés
    küldése kiosztás-váltáskor, lásd routes/postproduction.py, routes/tasks.py). `data` a
    ténylegesen PATCH-elt scalar mezőket tartalmazza (a payload kulcsaival), `m2m_changes`
    pedig {payload_key: {"added": {id, ...}, "removed": {id, ...}}} minden érintett m2m mezőhöz.

    before_delete: DELETE előtt hívódik (obj, db) paraméterekkel - HTTPException-t
    dobhat, ha a rekord nem törölhető (pl. a projekthez tartozó Média Portál
    tartalmát nem szabad mellékhatásként elveszíteni, lásd routes/projects.py).

    entity_type: ha meg van adva, PATCH-nél a payloadban érintett mezőket a
    services/detail_tabs.get_field_tab_map alapján fülekre bontja, és minden
    érintett fülhöz külön ellenőrzi a "{page}:{tab_key}" összetett kulccsal az
    "edit" jogot (lásd core/security.check_tab_action) - így egy admin
    korlátozhatja, hogy egy felhasználó csak bizonyos fülök mezőit
    szerkeszthesse (a durvább, oldal-szintű edit_dependency ellenőrzés MELLETT).
    Ha nincs megadva, a viselkedés változatlan (csak az oldal-szintű ellenőrzés fut).

    sor_szuro: (stmt, db, current_user) -> stmt - SORONKÉNTI láthatóság. A
    lista-lekérdezésre kerül rá, az egyedi GET/PATCH/DELETE pedig 404-gyel
    válaszol, ha az adott rekord nem fér bele. Erre a korlátozott fiókoknál
    van szükség: egy külsős vágó csak a SAJÁT anyagát láthatja, semmi mást
    (lásd core/security.lathato_anyagok). Ha nincs megadva, mindenki minden
    sort lát (a korábbi viselkedés)."""
    router = APIRouter(prefix=prefix, tags=tags)
    role_dependency = require_roles(*write_roles) if write_roles else get_current_user
    m2m_fields = m2m_fields or {}
    list_read_schema = list_read_schema or read_schema

    def _action_dependency(action: str):
        def dependency(current_user: Employee = Depends(role_dependency), db: Session = Depends(get_db)) -> Employee:
            check_page_action(db, current_user, page, action)
            return current_user

        return dependency

    create_dependency = _action_dependency("create")
    edit_dependency = _action_dependency("edit")
    delete_dependency = _action_dependency("delete")

    def _get_or_404(db: Session, obj_id: int) -> Any:
        obj = db.get(model, obj_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} nem található")
        return obj

    def _apply_m2m(obj: Any, data: dict, db: Session) -> None:
        for payload_key, (attr_name, related_model) in m2m_fields.items():
            if payload_key not in data:
                continue
            ids = data.pop(payload_key)
            related = db.scalars(select(related_model).where(related_model.id.in_(ids))).all() if ids else []
            setattr(obj, attr_name, related)

    column_names = set(model.__table__.columns.keys())

    def _kimenet(
        obj: Any,
        schema: type[BaseModel],
        db: Session,
        *,
        sajat_mezokkel: bool,
        eltavolitott: set[str] | None = None,
    ) -> dict:
        """A válasz JSON-ja, az entitáshoz beállított mezőkkel: az eltávolított
        mezők KIMARADNAK, a saját (admin által létrehozott) mezők pedig
        bekerülnek - így a frontendnek nem kell tudnia róluk, mindenhol úgy
        viselkednek, mint bármelyik valódi oszlop (lásd services/entity_fields.py).
        Ha ehhez az entitáshoz nincs se eltávolított, se saját mező, a séma
        kimenete változatlanul megy tovább.

        `eltavolitott`: az eltávolított mezők halmaza. LISTÁNÁL a hívó adja át,
        egyszer lekérdezve - enélkül soronként futna egy lekérdezés, ami több
        száz soros listánál önmagában több száz felesleges kört jelentene."""
        adat = schema.model_validate(obj).model_dump(mode="json")
        if entity_type is None:
            return adat
        if eltavolitott is None:
            eltavolitott = entity_fields.hidden_fields(db, entity_type)
        for field in eltavolitott:
            adat.pop(field, None)
        if sajat_mezokkel:
            adat.update(entity_fields.values_for_record(db, entity_type, obj.id))
        return adat

    # response_model helyett kézzel szerializálunk (lásd _kimenet): a FastAPI
    # response_model visszavágná a saját mezőket és visszatenné az
    # eltávolítottakat, mert a séma mezőlistája fix.
    @router.get("", response_model=None)
    def list_items(
        request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
    ):
        """A skip/limit mellett bármelyik valódi oszlop szerint szűrhető query
        param-mal (pl. ?project_code_id=5) - ez adja a kapcsolódó rekordok
        (pl. egy Project Code összes Projektje) frontend-oldali lekérdezését.
        Bejelentkezés nélkül semmilyen adat nem érhető el (lásd get_current_user)."""
        stmt = select(model)
        if sor_szuro is not None:
            stmt = sor_szuro(stmt, db, _user)
        # Több rekord EGY kérésben, id-lista alapján (?ids=1,2,3): a frontend
        # getRecordsByIds korábban rekordonként külön HTTP-kérést indított -
        # egy sok-forgatásos eszköz adatlapja több száz párhuzamos kérést lőtt
        # ki, ami kimerítette az adatbázis-kapcsolatokat és mindenki másnak
        # megakasztotta a rendszert.
        ids_param = request.query_params.get("ids")
        if ids_param:
            try:
                id_lista = [int(x) for x in ids_param.split(",") if x.strip()]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Az ids paraméter csak számokat tartalmazhat."
                ) from None
            stmt = stmt.where(model.id.in_(id_lista))
        # Eager load a lista-lekérdezéshez: ha a read séma számított mezői
        # kapcsolatokat járnak be (pl. ProjectCode.osszes_koltseg), azok
        # enélkül SORONKÉNT indítanának külön lekérdezést.
        if list_options:
            stmt = stmt.options(*list_options)
        for key, raw_value in request.query_params.items():
            if key in ("skip", "limit") or key not in column_names:
                continue
            try:
                value: Any = int(raw_value)
            except ValueError:
                value = raw_value
            stmt = stmt.where(getattr(model, key) == value)
        # A legutóbb módosított/létrehozott rekordok jöjjenek elöl - enélkül a
        # lapozás (skip/limit) tetszőleges, DB-függő sorrendben adná vissza a
        # sorokat, és a frontend "elsőként a friss, régieket később a
        # háttérben" betöltési mintája (lásd pl. app/(app)/utomunka/page.tsx)
        # nem érné el a célját, mert az "első lap" nem a friss rekordokat adná.
        order_column = getattr(model, "updated_at", None)
        stmt = stmt.order_by(order_column.desc() if order_column is not None else model.id.desc())
        sorok = db.scalars(stmt.offset(skip).limit(limit)).all()
        # Az eltávolított mezőket EGYSZER kérdezzük le az egész listára.
        eltavolitott = entity_fields.hidden_fields(db, entity_type) if entity_type else set()
        # A listákba a saját mezők értékei nem kerülnek bele (rekordonként
        # külön lekérdezés lenne) - a részletnézeten viszont ott vannak.
        eredmeny = [
            _kimenet(o, list_read_schema, db, sajat_mezokkel=False, eltavolitott=eltavolitott) for o in sorok
        ]
        return kimenet_szuro(eredmeny, db, _user) if kimenet_szuro else eredmeny

    def _szurt_kimenet(adat: dict, db: Session, user: Employee) -> dict:
        """Az egy-rekordos válaszokra is lefut a kimenet_szuro - listába
        csomagolva, mert a szűrő listát vár (lásd a paraméter kommentjét)."""
        return kimenet_szuro([adat], db, user)[0] if kimenet_szuro else adat

    def _lathato_vagy_404(db: Session, item_id: int, user: Employee):
        """A rekord, ha ez a felhasználó láthatja - különben 404 (nem 403: egy
        korlátozott fióknak az sem információ, hogy létezik-e a rekord)."""
        obj = _get_or_404(db, item_id)
        if sor_szuro is not None:
            engedett = db.scalar(sor_szuro(select(model.id).where(model.id == item_id), db, user))
            if engedett is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rekord nem található")
        return obj

    @router.get("/{item_id}", response_model=None)
    def get_item(item_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
        return _szurt_kimenet(
            _kimenet(_lathato_vagy_404(db, item_id, _user), read_schema, db, sajat_mezokkel=True), db, _user
        )

    # A before_create hook kaphatja a bejelentkezett embert is harmadik
    # paraméterként - a paraméterszámot egyszer, a router építésekor nézzük
    # meg, nem minden kérésnél (lásd a before_create paraméter kommentjét).
    before_create_kell_user = before_create is not None and len(inspect.signature(before_create).parameters) >= 3

    @router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
    def create_item(payload: create_schema, db: Session = Depends(get_db), _user: Employee = Depends(create_dependency)):
        data = payload.model_dump()
        m2m_data = {k: data.pop(k) for k in list(m2m_fields) if k in data}
        if before_create:
            data = before_create(data, db, _user) if before_create_kell_user else before_create(data, db)
        obj = model(**data)
        for payload_key, ids in m2m_data.items():
            attr_name, related_model = m2m_fields[payload_key]
            related = db.scalars(select(related_model).where(related_model.id.in_(ids))).all() if ids else []
            setattr(obj, attr_name, related)
        db.add(obj)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Az érték már foglalt (egyedinek kell lennie)."
            ) from exc
        db.refresh(obj)
        return _szurt_kimenet(_kimenet(obj, read_schema, db, sajat_mezokkel=True), db, _user)

    @router.patch("/{item_id}", response_model=None)
    async def update_item(
        item_id: int,
        request: Request,
        db: Session = Depends(get_db),
        current_user: Employee = Depends(edit_dependency),
    ):
        """A payload egy nyers JSON objektum (nem egy fix update_schema) - bármelyik
        valódi oszlop PATCH-elhető vele (a hashed_password/id kivételével), hogy a
        részletnézeten bármelyik mező helyben szerkeszthető legyen (lásd
        EditableDetailGrid a frontenden), anélkül hogy minden entitáshoz kézzel
        karban kellene tartani egy külön Update sémát a ~50-140 mezőhöz."""
        obj = _lathato_vagy_404(db, item_id, current_user)
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A kérés törzsének JSON objektumnak kell lennie")

        m2m_changes: dict[str, dict[str, set[int]]] = {}
        for payload_key in list(m2m_fields):
            if payload_key in data:
                ids = set(data.pop(payload_key) or [])
                attr_name, related_model = m2m_fields[payload_key]
                previous_ids = {r.id for r in getattr(obj, attr_name)}
                related = db.scalars(select(related_model).where(related_model.id.in_(ids))).all() if ids else []
                setattr(obj, attr_name, related)
                m2m_changes[attr_name] = {"added": ids - previous_ids, "removed": previous_ids - ids}

        if entity_type:
            field_tab_map = get_field_tab_map(db, entity_type)
            touched_tabs = {
                field_tab_map.get(field, OTHER_TAB_KEY)
                for field in data.keys()
                if field not in _PATCH_DENYLIST and field in column_names
            }
            for tab_key in touched_tabs:
                check_tab_action(db, current_user, page, tab_key, "edit")

        # A SAJÁT (admin által létrehozott) mezők értékei nem oszlopok, hanem
        # külön táblában vannak - ezeket innen emeljük ki, hogy a felületnek ne
        # kelljen külön végpontot hívnia: a részletnézet ugyanúgy PATCH-eli
        # őket, mint bármelyik valódi mezőt (lásd services/entity_fields.py).
        if before_update:
            before_update(obj, data, db, current_user)

        eltavolitott = entity_fields.hidden_fields(db, entity_type) if entity_type else set()
        sajat_ertekek = (
            {k: v for k, v in data.items() if k in entity_fields.custom_keys(db, entity_type)} if entity_type else {}
        )

        columns = model.__table__.columns
        for field, value in data.items():
            # Az eltávolított mező nem része a rendszernek: az értéke akkor sem
            # írható felül, ha valaki (pl. egy régi, még nyitva lévő fül)
            # elküldi.
            if field in _PATCH_DENYLIST or field in eltavolitott or field not in column_names:
                continue
            try:
                setattr(obj, field, _coerce_value(columns[field], value))
            except (ValueError, TypeError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Érvénytelen érték a '{field}' mezőhöz: {exc}"
                ) from exc
        if sajat_ertekek and entity_type:
            entity_fields.set_values(db, entity_type, obj.id, sajat_ertekek)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Az érték már foglalt (egyedinek kell lennie)."
            ) from exc
        db.refresh(obj)
        if after_update:
            after_update(obj, data, m2m_changes, db, current_user)
        return _szurt_kimenet(_kimenet(obj, read_schema, db, sajat_mezokkel=True), db, current_user)

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_item(item_id: int, db: Session = Depends(get_db), _user: Employee = Depends(delete_dependency)):
        obj = _lathato_vagy_404(db, item_id, _user)
        if before_delete:
            before_delete(obj, db)
        if entity_type:
            # A saját mezők értékeit nem idegen kulcs köti a rekordhoz (a tábla
            # generikus), ezért kézzel kell vinni őket a rekorddal együtt.
            entity_fields.delete_values_for_record(db, entity_type, obj.id)
        # Ugyanez a Notion-leképezésre: ha itt maradna, az adott Notion-oldal
        # kiesne az importból (lásd services/notion_mapping.py). Az importer az
        # OSZTÁLYNEVET használja entitástípusként ("Contract", "Employee").
        notion_mapping.torold_a_leképezest(db, model.__name__, obj.id)
        db.delete(obj)
        try:
            db.commit()
        except IntegrityError as exc:
            # Maradt olyan kapcsolódó rekord, ami hivatkozik erre a sorra (vagy
            # egy nem-nullázható idegen kulcsot próbáltunk nullázni). Enélkül a
            # felhasználó csak egy "Váratlan szerverhiba történt." üzenetet
            # látott, amiből semmi nem derült ki.
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A rekord nem törölhető, mert még hivatkoznak rá más rekordok. "
                    f"Előbb töröld vagy oldd le azokat. ({model.__name__} #{item_id})"
                ),
            ) from exc

    return router
