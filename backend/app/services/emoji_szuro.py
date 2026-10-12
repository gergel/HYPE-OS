"""EMOJI-SZŰRŐ az AI által írt szövegekhez (a felhasználó kérése: ha az AI
felvezet egy leírást vagy kommentet, abba emoji ne kerüljön - a vágás
leírásában a "⏱️ SÜRGŐS", "🔤 STÍLUSELEM" zavaró volt).

Csak az emojikat és a hozzájuk tartozó láthatatlan jeleket (változat-választó,
nulla szélességű kötő, billentyűsapka) veszi ki; a magyar ékezetes betűk, a
tipográfiai jelek (– „ ” → ©) és a markdown-jelölés érintetlen marad. Ahol
egy emoji kiesett, a sor elejéről/közepéről a fölösleges szóköz is eltűnik
("### 🔤 CÍM" -> "### CÍM"), a behúzás viszont megmarad (beágyazott lista)."""

from __future__ import annotations

import re

_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # képírás-jelek, hangulatjelek, közlekedés, zászlók, kiegészítők
    "☀-➿"  # vegyes szimbólumok és dingbatok (☀ ✅ ✨ ❗ ❤ ✔)
    "⌀-⏿"  # technikai jelek közül az emoji-szerűek (⌚ ⏰ ⏱ ⏳)
    "⬀-⯿"  # ⭐ ⬆ ⬛ és társai
    "〰〽㊗㊙"
    "︎️"  # változat-választók
    "‍"  # nulla szélességű kötő (összetett emojik)
    "⃣"  # billentyűsapka (1️⃣)
    "]+"
)
_SOK_SZOKOZ = re.compile(r"(?<=\S)[ \t]{2,}")
_JELOLO_UTAN = re.compile(r"^(\s*(?:#{1,6}|[-*+]|\d+[.)]|>)\s)\s+")


def emoji_nelkul(szoveg: str) -> str:
    """A szöveg emojik nélkül; ahol nem volt emoji, a sor változatlan."""
    if not _EMOJI.search(szoveg):
        return szoveg
    sorok = []
    for sor in szoveg.split("\n"):
        uj = _EMOJI.sub("", sor)
        if uj != sor:
            behuzas = sor[: len(sor) - len(sor.lstrip())]
            uj = _SOK_SZOKOZ.sub(" ", uj.strip())
            uj = _JELOLO_UTAN.sub(r"\1", uj)
            uj = behuzas + uj
        sorok.append(uj)
    return "\n".join(sorok)


def emoji_nelkul_melyen(adat):
    """Egy kérés-törzs (dict/list/str) összes szövegéből kiveszi az emojikat."""
    if isinstance(adat, str):
        return emoji_nelkul(adat)
    if isinstance(adat, dict):
        return {k: emoji_nelkul_melyen(v) for k, v in adat.items()}
    if isinstance(adat, list):
        return [emoji_nelkul_melyen(v) for v in adat]
    return adat
