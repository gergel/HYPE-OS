"""Vágói visszajelzések - amit a vágók írnak a leforgatott anyagról.

Ez a "gyűjtőhely": minden visszajelzés egy sorban, azzal együtt, amitől
használható lesz.

- KI írta és mikor;
- MELYIK anyagról, és hol a kész anyag (a link a visszajelzés pillanatában -
  lásd models/feedback.py);
- MELYIK FORGATÁSHOZ tartozik az az anyag, ha van hozzá forgatás;
- és ha van, KIK VOLTAK OTT azon a forgatáson.

Az utolsó pont adja az egésznek az értelmét: a vágó észrevétele annak szól,
aki forgatta. Ezért lehet innen egy gombbal kiküldeni a forgatás DISZPÓ-
LEVELÉRE válaszként - abba a szálba, amit a stáb már ismer.

Amit a levél tartalmaz, az szándékosan SZŰK: csak a szöveges megjegyzés és a
kész anyag linkje. A pontszámok belső mérőszámok, nem a stábnak szólnak - egy
"technikai helyesség: 6/10" a levélben számonkérésnek olvasódna, a szöveges
rész viszont pont az, amiből tanulni lehet."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_page_action
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.feedback import Feedback, VisszajelzesAllapot
from app.models.project import Project
from app.services import dispo
from app.services.google_email import send_message

router = APIRouter(prefix="/vagoi-visszajelzesek", tags=["postproduction"])

#: A visszajelzések az Utómunka oldalán születnek, és ott is olvassuk őket.
PAGE = "/utomunka"

#: Az Utómunka oldalon a durva szerepkör-kapu nem érvényes: aki a
#: Beállításokban /utomunka edit jogot kapott, az írhat - a szerepköre (vágó,
#: stb.) nem szűkíti tovább (ugyanaz az elv, mint routes/postproduction.py
#: _MINDEN_SZEREPKOR-jánál).
_MINDEN_SZEREPKOR = tuple(Role)


class ResztvevoRead(BaseModel):
    id: int
    full_name: str
    email: str | None = None


class VisszajelzesRead(BaseModel):
    id: int
    letrehozva: datetime

    #: Ki írta.
    visszajelzo_id: int | None = None
    visszajelzo_nev: str | None = None

    nyersanyag_felhasznalhatosaga: float | None = None
    technikai_helyesseg: float | None = None
    kreativ_kepivilag: float | None = None
    atlag: float | None = None
    megjegyzes: str | None = None

    deliverable_id: int
    deliverable_nev: str | None = None
    kesz_anyag_url: str | None = None

    #: A forgatás, amihez az anyag tartozik - lehet, hogy nincs ilyen (pl.
    #: archív anyagból készült vágás).
    project_id: int | None = None
    project_nev: str | None = None
    forgatas_datuma: str | None = None
    #: Kik voltak ott a forgatáson. Üres, ha nincs forgatás vagy nincs stáb.
    resztvevok: list[ResztvevoRead] = []

    diszpora_kikuldve: datetime | None = None
    #: uj | kikuldve | nem_kuldjuk - lásd models/feedback.VisszajelzesAllapot.
    allapot: str = VisszajelzesAllapot.UJ.value
    #: KIHAGYOTT visszajelzés: az automatikusan feldobott űrlapot indoklással
    #: átugorták - a megjegyzes maga az indok (lásd models/feedback.kihagyva).
    kihagyva: bool = False
    #: Kiküldhető-e a diszpóra: kell hozzá forgatás, címzett és megjegyzés -
    #: és az sem lehet, hogy eldöntöttük, ezt nem küldjük ki.
    kikuldheto: bool = False
    #: Ha nem küldhető ki, ez mondja meg, miért - a felület ezt írja ki a
    #: letiltott gomb mellé, hogy ne kelljen találgatni.
    kikuldes_akadalya: str | None = None


def _kikuldes_akadalya(feedback: Feedback, project: Project | None) -> str | None:
    """Miért nem küldhető ki ez a visszajelzés a diszpóra? None = kiküldhető."""
    # A kézi döntés a legerősebb: amiről kimondtuk, hogy marad nálunk, azt
    # semmilyen más feltétel nem teheti újra kiküldhetővé.
    if feedback.allapot == VisszajelzesAllapot.NEM_KULDJUK:
        return "Ezt a visszajelzést nem küldjük ki."
    if project is None:
        return "Ehhez az anyaghoz nincs forgatás."
    if not (feedback.visszajelzes_szoveg or "").strip():
        return "Nincs megjegyzés – a levélbe csak az menne ki."
    if not dispo._recipients(project):
        return "A forgatáshoz nincs egyetlen email cím sem."
    return None


def _kimenet(feedback: Feedback) -> VisszajelzesRead:
    deliverable = feedback.deliverable
    project = deliverable.project if deliverable is not None else None
    akadaly = _kikuldes_akadalya(feedback, project)
    return VisszajelzesRead(
        id=feedback.id,
        letrehozva=feedback.created_at,
        visszajelzo_id=feedback.visszajelzo_employee_id,
        visszajelzo_nev=feedback.visszajelzo.full_name if feedback.visszajelzo else None,
        nyersanyag_felhasznalhatosaga=(
            float(feedback.nyersanyag_felhasznalhatosaga) if feedback.nyersanyag_felhasznalhatosaga is not None else None
        ),
        technikai_helyesseg=float(feedback.technikai_helyesseg) if feedback.technikai_helyesseg is not None else None,
        kreativ_kepivilag=float(feedback.kreativ_kepivilag) if feedback.kreativ_kepivilag is not None else None,
        atlag=round(float(feedback.atlag), 1) if feedback.atlag is not None else None,
        megjegyzes=feedback.visszajelzes_szoveg,
        deliverable_id=feedback.deliverable_id,
        deliverable_nev=deliverable.projekt_neve if deliverable is not None else None,
        # A visszajelzésre mentett link az elsődleges (az anyagé azóta
        # változhatott); ha a régi sorokon még nincs, az anyagé segít ki.
        kesz_anyag_url=feedback.kesz_anyag_url or (deliverable.kesz_anyag_url if deliverable is not None else None),
        project_id=project.id if project is not None else None,
        project_nev=project.nev if project is not None else None,
        forgatas_datuma=project.forgatas_datuma.isoformat() if project is not None and project.forgatas_datuma else None,
        resztvevok=[
            ResztvevoRead(id=e.id, full_name=e.full_name, email=e.email) for e in (project.crew if project else [])
        ],
        diszpora_kikuldve=feedback.diszpora_kikuldve,
        allapot=feedback.allapot,
        kihagyva=feedback.kihagyva,
        kikuldheto=akadaly is None,
        kikuldes_akadalya=akadaly,
    )


@router.get("", response_model=list[VisszajelzesRead])
def list_visszajelzesek(
    deliverable_id: int | None = None,
    allapot: str | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """A visszajelzések, a legfrissebbel elöl.

    A kapcsolódó adatokat (anyag, forgatás, stáb, író) egyben töltjük be: a
    lista minden sorhoz mind a négyet kiírja, enélkül soronként több külön
    lekérdezés futna."""
    stmt = (
        select(Feedback)
        .options(
            selectinload(Feedback.visszajelzo),
            selectinload(Feedback.deliverable).selectinload(Deliverable.project).selectinload(Project.crew),
        )
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
    )
    if deliverable_id is not None:
        stmt = stmt.where(Feedback.deliverable_id == deliverable_id)
    if allapot:
        stmt = stmt.where(Feedback.allapot == allapot)
    return [_kimenet(f) for f in db.scalars(stmt).all()]


_LEVEL_HTML = """\
<p>Sziasztok,</p>
<p>
  Elkészült a vágás, és a vágóktól érkezett hozzá visszajelzés a forgatásról –
  megosztjuk veletek:
</p>
<blockquote style="margin: 12px 0; padding: 8px 14px; border-left: 3px solid #ddd; color: #333;">
  {megjegyzes}
</blockquote>
{link_resz}
<p>Köszönjük a munkátokat!</p>
"""

_LINK_HTML = '<p>A kész anyag: <a href="{url}">{url}</a></p>'


def _levelszoveg(feedback: Feedback, project: Project) -> str:
    """A kiküldött levél törzse.

    Két dolgot NEM írunk le, pedig kézenfekvő lenne: melyik forgatásról és
    melyik anyagról van szó. A levél az adott forgatás DISZPÓ-LEVELÉRE megy
    válaszként, tehát aki megkapja, pontosan tudja, melyik napról beszélünk -
    kiírva csak zaj lenne. Ami helyette hangsúlyos: a visszajelzés a VÁGÓKTÓL
    jön, nem a gyártástól.

    A tartalom így a szöveges megjegyzés és a kész anyag linkje - a
    pontszámok belső mérőszámok, azok nem mennek ki (lásd a modul kommentjét)."""
    url = feedback.kesz_anyag_url or (feedback.deliverable.kesz_anyag_url if feedback.deliverable else None)
    # A szöveg sortöréseit meg kell tartani: a vágó bekezdésekben ír.
    megjegyzes = (feedback.visszajelzes_szoveg or "").strip().replace("\n", "<br>")
    return _LEVEL_HTML.format(
        megjegyzes=megjegyzes,
        link_resz=_LINK_HTML.format(url=url) if url else "",
    )


ALLAPOTOK = [a.value for a in VisszajelzesAllapot]


class AllapotIn(BaseModel):
    allapot: str


@router.put("/{feedback_id}/allapot", response_model=VisszajelzesRead)
def set_allapot(
    feedback_id: int,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A visszajelzés állapotának kézi átállítása.

    Ez a "nem küldjük ki" döntés helye - és a visszavonásáé is: ami tévedésből
    került oda, azt vissza lehet állítani újnak. A KIKULDVE állapotot
    jellemzően a kiküldés írja be magától, de kézzel is beállítható (pl. ha a
    stáb a rendszeren kívül kapta meg)."""
    feedback = db.get(Feedback, feedback_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="A visszajelzés nem található.")
    if payload.allapot not in ALLAPOTOK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen állapot. Választható: {', '.join(ALLAPOTOK)}")
    feedback.allapot = payload.allapot
    db.commit()
    db.refresh(feedback)
    return _kimenet(feedback)


class KikuldesEredmeny(BaseModel):
    status: str
    message: str
    cimzettek: list[str] = []


@router.post("/{feedback_id}/diszpo-valasz", response_model=KikuldesEredmeny)
def diszpo_valasz(
    feedback_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A visszajelzés kiküldése a forgatás diszpó-levelére VÁLASZKÉNT.

    Ha a projektnek van már diszpó-szála (gmail_thread_id), abba válaszolunk -
    a stáb így a saját, ismerős levelezésében kapja meg, nem egy külön
    levélben. Ha nincs (nem innen ment ki a diszpó), sima levélként megy a
    forgatás résztvevőinek.

    A kiküldés tényét elmentjük, de ÚJRA is küldhető: a levél elveszhet, és
    egy második küldés semmit nem ront el."""
    feedback = db.get(Feedback, feedback_id)
    if feedback is None:
        raise HTTPException(status_code=404, detail="A visszajelzés nem található.")

    project = feedback.deliverable.project if feedback.deliverable else None
    akadaly = _kikuldes_akadalya(feedback, project)
    if akadaly is not None:
        raise HTTPException(status_code=400, detail=akadaly)
    assert project is not None  # az akadály-ellenőrzés már kizárta a None-t

    cimzettek = dispo._recipients(project)
    try:
        thread_id, _msg_id, rfc822 = send_message(
            cimzettek,
            # A diszpó tárgyára válaszolunk, hogy a szálban egyértelmű legyen,
            # melyik forgatásról van szó - a levél szövegének ezért nem kell
            # külön leírnia.
            f"Re: {dispo._subject(project)}",
            _levelszoveg(feedback, project) + dispo._SIGNATURE_HTML,
            thread_id=project.gmail_thread_id,
            in_reply_to=project.gmail_last_message_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    # A szálat frissítjük, hogy a KÖVETKEZŐ levél is ide fűződjön.
    project.gmail_thread_id = thread_id or project.gmail_thread_id
    project.gmail_last_message_id = rfc822 or project.gmail_last_message_id
    feedback.diszpora_kikuldve = datetime.now()
    feedback.allapot = VisszajelzesAllapot.KIKULDVE
    db.commit()

    return KikuldesEredmeny(
        status="OK",
        message=f"Kiküldve {len(cimzettek)} címzettnek a forgatás diszpó-szálába.",
        cimzettek=cimzettek,
    )
