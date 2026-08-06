"""Magyar hónapnevek - a Belsős TIG mindenhol BETŰVEL írja ki a hónapot
(dokumentumban, email tárgyában, kiadás megnevezésében), nem számmal."""

from datetime import date

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
