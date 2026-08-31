"""Magyar hónapnevek - a Belsős TIG mindenhol BETŰVEL írja ki a hónapot
(dokumentumban, email tárgyában, kiadás megnevezésében), nem számmal."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

#: A cég Budapesten dolgozik - ahol az számít, hogy "melyik nap/hónap van",
#: ott ezt kell nézni, nem a szerver óráját (a Railway UTC-ben jár, tehát
#: magyar idő szerint éjfél és hajnali 1-2 óra között a szerver még az ELŐZŐ
#: napot írná).
BUDAPEST_IDOZONA = ZoneInfo("Europe/Budapest")


def budapesti_ma() -> date:
    """A mai nap budapesti (magyar) idő szerint."""
    return datetime.now(BUDAPEST_IDOZONA).date()

HONAP_NEVEK = (
    "január",
    "február",
    "március",
    "április",
    "május",
    "június",
    "július",
    "augusztus",
    "szeptember",
    "október",
    "november",
    "december",
)


def honap_neve(honap: int) -> str:
    """1-12 -> "január" ... "december". Érvénytelen hónapra üres sztring, hogy
    egy hibás adat ne dobjon kivételt egy dokumentum-generálás közepén."""
    return HONAP_NEVEK[honap - 1] if 1 <= honap <= 12 else ""


def ev_honap_szoveg(ev: int, honap: int) -> str:
    """2026, 5 -> "2026. május"."""
    return f"{ev}. {honap_neve(honap)}"


def elozo_honap(nap: date) -> tuple[int, int]:
    """A teljesítés dátumából az általa igazolt hónap: MINDIG az azt megelőző
    hónap. Pl. 2026.06.20-i teljesítés a 2026. MÁJUSI TIG-hez tartozik."""
    return (nap.year - 1, 12) if nap.month == 1 else (nap.year, nap.month - 1)


def kovetkezo_honap_elseje(ev: int, honap: int) -> date:
    """Az elozo_honap() megfordítása: a hónapot KÖVETŐ hónap első napja."""
    return date(ev + 1, 1, 1) if honap == 12 else date(ev, honap + 1, 1)


#: A belsős TIG-et mindig a hónapot KÖVETŐ hónapban készítjük (júliusban a
#: júniusit, augusztusban a júliusit), és a teljesítés/fizetési határidő
#: ennek a hónapnak a 20-a - tehát a 2026. JÚNIUSI TIG-en 2026.07.20. áll.
TIG_HATARIDO_NAPJA = 20


def tig_hatarido(ev: int, honap: int) -> date:
    """Egy adott hónap belsős TIG-jének teljesítési és fizetési határideje: a
    KÖVETKEZŐ hónap 20-a."""
    return kovetkezo_honap_elseje(ev, honap).replace(day=TIG_HATARIDO_NAPJA)


def belsos_tig_honapja(
    ev: int,
    honap: int,
    teljesites_datuma: date | None = None,
    fizetesi_hatarido: date | None = None,
    utalas_datuma: date | None = None,
) -> tuple[int, int]:
    """Melyik hónap elszámolása ez a belsős TIG - MEGNEVEZÉSHEZ.

    A TIG mindig a hónapot KÖVETŐ hónapban készül, ezért a rajta lévő dátumok
    (teljesítés, fizetési határidő, utalás) is oda esnek: a 2026.07.20-i
    fizetési határidejű TIG a 2026. JÚNIUSI elszámolásé. Ahol tehát egy TIG-et
    névvel írunk ki, ott a dátumból számolunk vissza, és nem a tárolt (ev,
    honap) párt írjuk ki nyersen - így egy régi, elcsúszott bejegyzés is a
    helyes hónap nevével jelenik meg (a tárolt hónapot migráció igazítja, de a
    kiírásnak enélkül is stimmelnie kell).

    Dátum híján marad a tárolt hónap: nincs mihez visszaszámolni."""
    for datum in (teljesites_datuma, fizetesi_hatarido, utalas_datuma):
        if datum is not None:
            return elozo_honap(datum)
    return ev, honap
