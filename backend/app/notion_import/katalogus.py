"""Mit lehet importálni a Notionból - és mi honnan jön.

Eddig az import "mindent vagy semmit" volt: egyetlen gomb, ami mind a 25+
Notion-táblát végigfutotta, akár órákig (a Notion API rate limitje miatt). Ha
csak egyetlen tábla adata változott - mondjuk kézzel javítottak pár belsős
TIG-et -, akkor is az egészet újra kellett futtatni.

Ez a katalógus teszi választhatóvá az importot: soronként egy importer, a
FORRÁS Notion-táblákkal és a függőségeivel együtt. Ugyanez a lista szolgálja
ki a felületet (Beállítások > Notion import), a CLI-t (`--only`) és a teljes
importot - így nem tud szétcsúszni, mi választható és mi fut le.

A SORREND számít, és mindig ez a sorrend érvényes: a későbbi importerek a
korábbiak által létrehozott rekordokra hivatkoznak (a Notion relation-öket a
NotionImportMap táblán keresztül oldjuk fel). Ezért a részleges import is
ebben a sorrendben futtatja a kiválasztott elemeket, függetlenül attól, milyen
sorrendben pipálták ki őket.

A `fuggosegek` nem KÉNYSZER, csak figyelmeztetés alapja: ha egy korábbi
importban már bejöttek a projektek, a külsős papírokat önmagában is lehet
frissíteni. Csak az első, üres adatbázison induló importnál kell tényleg a
teljes sor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.notion_import import (
    importers,
    importers_belsos,
    importers_kulsos,
    importers_megrendeloi,
    importers_wave2,
    importers_wave3,
)


@dataclass(frozen=True)
class ImporterInfo:
    """Egy választható import-egység."""

    #: Technikai azonosító - ez megy az API-ba és a CLI `--only` kapcsolójába.
    #: NE változtasd meg feleslegesen: a felület ezzel hivatkozik rá.
    nev: str
    #: Emberi név a felületre.
    cimke: str
    #: Melyik körben fut (1/2/3) - a körök egymásra épülnek.
    kor: int
    #: Mely Notion-táblákból olvas.
    forrasok: tuple[str, ...]
    #: Mit hoz át, egy mondatban.
    leiras: str
    fn: Callable = field(compare=False, repr=False)
    #: Mely importereknek kell (legalább egyszer) lefutniuk előtte.
    fuggosegek: tuple[str, ...] = ()


KATALOGUS: tuple[ImporterInfo, ...] = (
    # ── 1. kör: törzsadatok, amikre minden más hivatkozik ────────────────────
    ImporterInfo(
        nev="Client+Contact",
        cimke="Ügyfelek és kontaktok",
        kor=1,
        forrasok=("Megrendelői kontaktok",),
        leiras="Ügyfélcégek és a hozzájuk tartozó kapcsolattartók.",
        fn=importers.import_clients_and_contacts,
    ),
    ImporterInfo(
        nev="Employee",
        cimke="Munkatársak",
        kor=1,
        forrasok=("Külsős és belsős", "Vágók"),
        leiras="A teljes crew-névsor: belsősök, külsősök, vágók - cégadatokkal együtt.",
        fn=importers.import_employees,
    ),
    ImporterInfo(
        nev="Rate",
        cimke="Bérezés (óra-/napidíj)",
        kor=1,
        forrasok=("Órabér/Napibér",),
        leiras="Munkatársankénti órabér, napidíj, havi alap.",
        fn=importers.import_rates,
        fuggosegek=("Employee",),
    ),
    ImporterInfo(
        nev="Equipment",
        cimke="Eszközök",
        kor=1,
        forrasok=("Leltár",),
        leiras="A technikai leltár. Semmilyen más importtól nem függ.",
        fn=importers.import_equipment,
    ),
    ImporterInfo(
        nev="Campaign",
        cimke="Kampányok",
        kor=1,
        forrasok=("Kampányok",),
        leiras="Kampányok és állapotuk.",
        fn=importers.import_campaigns,
    ),
    ImporterInfo(
        nev="Task",
        cimke="Feladatok",
        kor=1,
        forrasok=("Teendők", "Agi todo list", "HYPE todo list", "Archive feladatok"),
        leiras="A négy Notion-teendőlista egyben; az archív feladatok archivált állapottal.",
        fn=importers.import_tasks,
        fuggosegek=("Employee",),
    ),
    ImporterInfo(
        nev="Contract",
        cimke="Keretszerződések",
        kor=1,
        forrasok=("Keretszerződés", "Alvállalkozó keretszerződés (külsős)"),
        leiras=(
            "Ügyfél- és alvállalkozói keretszerződések. A kézzel karbantartott "
            "keretszerződés-listát NEM írja felül: csak fájlokat tölt fel és állapotot "
            "frissít, embert nem vesz fel és nem vesz le."
        ),
        fn=importers.import_contracts,
        fuggosegek=("Employee", "Client+Contact"),
    ),
    ImporterInfo(
        nev="ProjectCode",
        cimke="Projektkódok",
        kor=1,
        forrasok=("HYPE ADMIN projektkódok",),
        leiras="A projektkódok és pénzügyi állapotuk.",
        fn=importers.import_project_codes,
        fuggosegek=("Client+Contact",),
    ),
    # ── 2. kör: a projektekre épülő adat ─────────────────────────────────────
    ImporterInfo(
        nev="Project",
        cimke="Projektek (forgatások)",
        kor=2,
        forrasok=("Main Database",),
        leiras="A forgatások, stáblistával és diszpó-állapottal.",
        fn=importers_wave2.import_projects,
        fuggosegek=("Employee", "ProjectCode"),
    ),
    ImporterInfo(
        nev="Deliverable",
        cimke="Utómunkák",
        kor=2,
        forrasok=("Utómunka",),
        leiras="A vágandó/kiadandó anyagok, vágóval és határidővel.",
        fn=importers_wave2.import_deliverables,
        fuggosegek=("Project",),
    ),
    ImporterInfo(
        nev="Timesheet",
        cimke="Időmérések",
        kor=2,
        forrasok=("Timesheet Public", "Timesheet Private"),
        leiras="A vágásra fordított idő mérései.",
        fn=importers_wave2.import_timesheets,
        fuggosegek=("Deliverable",),
    ),
    ImporterInfo(
        nev="Expense",
        cimke="Kiadások",
        kor=2,
        forrasok=("Kiadások", "Projekt kiadások", "Belsős extra kiadások"),
        leiras="Minden kiadás-sor a pénzügyi kimutatáshoz.",
        fn=importers_wave2.import_expenses,
        fuggosegek=("ProjectCode", "Employee"),
    ),
    ImporterInfo(
        nev="Revenue",
        cimke="Bevételek",
        kor=2,
        forrasok=("Bevételek",),
        leiras="Bevétel-sorok, számlázási és fizetési dátumokkal.",
        fn=importers_wave2.import_revenues,
        fuggosegek=("ProjectCode",),
    ),
    ImporterInfo(
        nev="KpForgalom",
        cimke="KP forgalom",
        kor=2,
        forrasok=("KP forgalom",),
        leiras="Készpénzes forgalom.",
        fn=importers_wave2.import_kp_forgalom,
    ),
    ImporterInfo(
        nev="Feedback",
        cimke="Visszajelzések",
        kor=2,
        forrasok=("Visszajelzések",),
        leiras="Ügyfél-visszajelzések a projektekre.",
        fn=importers_wave2.import_feedback,
        fuggosegek=("Project",),
    ),
    ImporterInfo(
        nev="Contract+TIG (Külsős)",
        cimke="Külsős papírok (eseti szerződés + TIG)",
        kor=2,
        forrasok=("Külsős",),
        leiras=(
            "A külsősök PROJEKTENKÉNTI papírjai: eseti szerződés és teljesítési "
            "igazolás, állapottal, összeggel és a feltöltött fájlokkal."
        ),
        fn=importers_kulsos.import_kulsos_papirok,
        fuggosegek=("Project", "Employee"),
    ),
    ImporterInfo(
        nev="Megrendelői papírok",
        cimke="Megrendelői papírok (eseti szerződés + TIG)",
        kor=2,
        forrasok=("HYPE ADMIN projektkódok",),
        leiras=(
            "A projektkódokhoz a Notionban feltöltött MEGRENDELŐI eseti szerződések és "
            "teljesítési igazolások - névvel, dátummal, összeggel és magával a papírral. "
            "Nem hív Notiont: a már importált projektkódokból és csatolmányokból dolgozik, "
            "ezért a ProjectCode import UTÁN kell futnia."
        ),
        fn=importers_megrendeloi.import_megrendeloi_papirok,
        fuggosegek=("ProjectCode",),
    ),
    # ── 3. kör: egyedi logikájú maradék ──────────────────────────────────────
    ImporterInfo(
        nev="Assignment (Stock igények)",
        cimke="Eszközfoglalások (Stock igények)",
        kor=3,
        forrasok=("Stock igények",),
        leiras="Melyik eszköz melyik forgatáson volt lefoglalva.",
        fn=importers_wave3.import_stock_igenyek,
        fuggosegek=("Equipment", "Project"),
    ),
    ImporterInfo(
        nev="Expense (Geri elszámolás)",
        cimke="Kiadások (Geri elszámolás)",
        kor=3,
        forrasok=("Geri elszámolás",),
        leiras="A külön vezetett elszámolás kiadás-sorai.",
        fn=importers_wave3.import_geri_elszamolas,
        fuggosegek=("ProjectCode",),
    ),
    ImporterInfo(
        nev="Media (Törölt anyagok)",
        cimke="Törölt anyagok",
        kor=3,
        forrasok=("Törölt anyagok",),
        leiras="A törölt médiafájlok nyilvántartása.",
        fn=importers_wave3.import_torolt_anyagok,
        fuggosegek=("Project",),
    ),
    ImporterInfo(
        nev="BelsosTig",
        cimke="Belsős TIG-ek és számlák",
        kor=3,
        forrasok=("Belsős", "Belsős extra kiadások"),
        leiras=(
            "A belsősök havi TIG-jei: összeg, teljesítés/keltezés, a TIG dokumentuma, "
            "a feltöltött számlák, és hogy ki van-e fizetve."
        ),
        fn=importers_belsos.import_belsos_tig,
        # Az extráit összekötjük az ugyanabból a Notion-oldalból készült
        # Expense sorral, ezért a Kiadások után kell futnia.
        fuggosegek=("Employee", "Expense"),
    ),
)

#: Név -> leíró. A keresés kis/nagybetűre érzéketlen (a CLI-ből bármit írnak).
_NEV_SZERINT = {info.nev.lower(): info for info in KATALOGUS}


def keres(nev: str) -> ImporterInfo | None:
    """Egy importer a nevéből. Ismeretlen névnél None - a hívó így a
    NotionClient() (és a NOTION_API_KEY-igény) ELŐTT tud hibát jelezni."""
    return _NEV_SZERINT.get((nev or "").strip().lower())


def valogat(nevek: list[str] | None) -> list[ImporterInfo]:
    """A kiválasztott importerek, MINDIG a katalógus sorrendjében.

    Üres/None kérésnél az egészet adja vissza - ez a "futtass mindent" eset.
    A sorrend azért nem a kérésé, mert a körök egymásra épülnek: hiába pipálja
    ki valaki előbb a Külsős papírokat és utána a Projekteket, a projekteknek
    kell előbb lefutniuk."""
    if not nevek:
        return list(KATALOGUS)
    kert = {(n or "").strip().lower() for n in nevek}
    return [info for info in KATALOGUS if info.nev.lower() in kert]


def ismeretlen_nevek(nevek: list[str]) -> list[str]:
    """A kérésben szereplő, katalógusban nem létező nevek - elgépelésre."""
    return [n for n in nevek if keres(n) is None]


def hianyzo_fuggosegek(kivalasztott: list[ImporterInfo]) -> dict[str, list[str]]:
    """Mely kiválasztott elemek függősége maradt ki a kijelölésből.

    Csak FIGYELMEZTETÉS: ha az adott adat egy korábbi importból már megvan, a
    részleges futtatás így is helyes. Az első, üres adatbázison induló
    importnál viszont ez árulja el, miért nem talál semmit."""
    bent = {info.nev for info in kivalasztott}
    return {
        info.nev: [f for f in info.fuggosegek if f not in bent]
        for info in kivalasztott
        if any(f not in bent for f in info.fuggosegek)
    }
