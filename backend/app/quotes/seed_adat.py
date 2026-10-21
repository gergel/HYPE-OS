"""Az árajánlat-készítő alapadatai (a specifikáció 6-8. pontja).

Az árak 473 korábbi HYPE-árajánlat (2023.12-2026.09) elemzéséből jönnek: az
alapár a legfrissebb tipikus ár, a min-max tájékoztató. Minden nettó forint.
A leírásokban a sortörés `\\n`; a „- ” kezdetű sorok felsorolásként jelennek meg."""

from __future__ import annotations

KATEGORIAK = ["Stáb", "Fotó", "Eszköz", "LED fal", "Utómunka", "Előkészítés", "Egyéb"]

#: (#, kategória, név, leírás, egység, alapár, min, max)
TETELEK: list[tuple[int, str, str, str, str, int, int | None, int | None]] = [
    (1, "Stáb", "Operatőr", "- 1 forgatási nap (max. 8 óra)", "fo_nap", 80000, 60000, 120000),
    (2, "Stáb", "Operatőr túlóra", "8 munkaórát meghaladóan fizetendő", "ora", 10500, None, None),
    (3, "Stáb", "Vezető operatőr", "", "fo_nap", 100000, 85000, 120000),
    (4, "Stáb", "Drón operatőr", "", "fo_nap", 75000, None, None),
    (5, "Stáb", "FPV drón operatőr", "", "fo_nap", 100000, None, None),
    (6, "Stáb", "Rendező", "", "nap", 100000, 100000, 150000),
    (7, "Stáb", "Kreatív director", "", "project", 100000, 90000, 120000),
    (8, "Stáb", "Technikai vezető", "", "nap", 100000, 80000, 150000),
    (9, "Stáb", "Adásrendező", "", "nap", 120000, 85000, 150000),
    (10, "Stáb", "Képvágó", "élő képkeverés", "fo_nap", 85000, 85000, 95000),
    (11, "Stáb", "Képmérnök", "", "fo_nap", 85000, None, None),
    (12, "Stáb", "Stream technikus", "", "fo_nap", 85000, 60000, 100000),
    (13, "Stáb", "Technikus", "", "fo_nap", 70000, 50000, 100000),
    (14, "Stáb", "Hangmérnök", "", "fo_nap", 75000, 50000, 100000),
    (15, "Stáb", "Világosító", "", "fo_nap", 100000, 75000, 100000),
    (16, "Stáb", "Bejátszó / feliratozó operátor", "", "fo_nap", 100000, 65000, 100000),
    (17, "Stáb", "Hálózat technikus", "", "fo_nap", 100000, None, None),
    (18, "Stáb", "Stage manager / floor manager", "", "fo_nap", 85000, None, None),
    (19, "Stáb", "Helyszíni vágó", "- napi highlight videó készítése a helyszínen", "fo_nap", 80000, 70000, 80000),
    (20, "Stáb", "D.I.T.", "", "nap", 85000, None, None),
    (21, "Stáb", "Szerkesztő-riporter", "", "nap", 100000, 90000, 100000),
    (22, "Stáb", "Sminkes", "szükséges felszereléssel", "fo_nap", 100000, 100000, 120000),
    (23, "Stáb", "Fodrász", "szükséges felszereléssel", "fo_nap", 120000, 100000, 120000),
    (24, "Stáb", "Stylist", "", "nap", 80000, 70000, 200000),
    (25, "Stáb", "Narrátor", "narráció felvétele", "project", 70000, 40000, 70000),
    (26, "Stáb", "Project menedzsment",
     "- folyamatos kapcsolattartás az ügyféllel\n- előzetes egyeztetések, helyszínbejárás",
     "project", 250000, 80000, 1750000),
    (27, "Fotó", "Fotós felszereléssel, kidolgozott képgaléria leadásával", "", "fo_nap", 100000, 70000, 150000),
    (28, "Fotó", "Fotós, azonnali helyszíni fotóleadással", "", "fo_nap", 90000, None, None),
    (29, "Fotó", "Fotó utómunka", "- retus", "project", 100000, None, None),
    (30, "Fotó", "Alap világítástechnikai eszközök fotózáshoz", "", "nap", 60000, None, None),
    (31, "Eszköz", "Panasonic Lumix S5IIX kameraszett", "kamera, optika, akkumulátorok, kártyák",
     "db_nap", 30000, None, None),
    (32, "Eszköz", "RED Komodo 6K cinema kameraszett", "", "db_nap", 40000, None, None),
    (33, "Eszköz", "Blackmagic Pocket 6K kameraszett", "", "db_nap", 40000, None, None),
    (34, "Eszköz", "Broadcast kamera szett", "", "db_nap", 40000, None, None),
    (35, "Eszköz", "Broadcast optikasor", "", "nap", 90000, 15000, 90000),
    (36, "Eszköz", "RF (vezeték nélküli) kameraszett", "pl. Ronin 4D", "db_nap", 150000, 150000, 200000),
    (37, "Eszköz", "GoPro szett", "", "db_nap", 15000, None, None),
    (38, "Eszköz", "Kameramozgató (gimbal)", "", "db_nap", 7500, None, None),
    (39, "Eszköz", "Kameramozgató (motoros slider)", "", "db_nap", 45000, None, None),
    (40, "Eszköz", "6m jimmy jib", "", "nap", 175000, 170000, 250000),
    (41, "Eszköz", "DJI Mavic drón szett", "", "db_nap", 45000, 30000, 60000),
    (42, "Eszköz", "FPV drón szett", "", "db_nap", 50000, None, None),
    (43, "Eszköz", "Légtérengedély ügyintézés", "adminisztratív költség / helyszín", "alkalom", 75000, 70000, 500000),
    (44, "Eszköz", "Alap világítástechnikai eszközök", "", "nap", 30000, None, None),
    (45, "Eszköz", "LED lámpaszett", "", "nap", 15000, None, None),
    (46, "Eszköz", "Mikroport szett", "", "db_nap", 10000, 10000, 15000),
    (47, "Eszköz", "Riporter mikrofon szett", "", "db_nap", 10000, None, None),
    (48, "Eszköz", "Hangrögzítéshez szükséges eszközök", "boom, Zoom hangrögzítő, mikroport",
     "nap", 10000, 10000, 30000),
    (49, "Eszköz", "Hangtechnikai eszközök rendezvényhez",
     "- 2 db aktív hangfal állványon\n- hangkeverőpult\n- kábelek", "nap", 150000, 50000, 250000),
    (50, "Eszköz", "Hangosítás (kis rendszer)", "- 2 db aktív hangfal állványon\n- keverőpult",
     "nap", 50000, 50000, 75000),
    (51, "Eszköz", "Rendezői monitor", "", "nap", 30000, None, None),
    (52, "Eszköz", "Mobil munkaállomás, képmixer, üzemeltetési eszközök", "stream / élő képkeverés",
     "nap", 190000, 75000, 350000),
    (53, "Eszköz", "1 kamerás közvetítés (csomag)", "- 1 db HD kamera\n- streaming munkaállomás\n- 1 fő operatőr",
     "alkalom", 300000, None, None),
    (54, "Eszköz", "HD broadcast közvetítő egység (OB van)",
     "- ATEM 4K M/E képkeverő\n- képmérnöki pult\n- digitális audiopult\n- rögzítés, streaming encoder\n- intercom",
     "nap", 1100000, 150000, 1750000),
    (55, "Eszköz", "Vezeték nélküli utasítórendszer", "4 csatornás", "nap", 45000, 20000, 125000),
    (56, "Eszköz", "Mobilinternet", "közvetítéshez", "nap", 30000, 30000, 150000),
    (57, "Eszköz", "Mobil vágó munkaállomás", "- célhardver\n- szoftver és licenszek", "nap", 100000, 70000, 100000),
    (58, "Eszköz", "Adatmentés és rögzítés, tárhely", "", "project", 200000, 45000, 900000),
    (59, "Eszköz", "Háttér, háttértartók / greenbox", "", "nap", 50000, 30000, 50000),
    (60, "Eszköz", "Stúdió bérlés", "", "nap", 75000, 42000, 150000),
    (61, "Eszköz", "Súgógép", "", "nap", 30000, None, None),
    (62, "Eszköz", "Projektor / vetítéstechnika", "", "nap", 100000, None, None),
    (63, "LED fal", "15 m² LED fal (P4.8)",
     "- P4.8-as LED fal elemekből\n- vezérlő, üzemeltetési eszközök\n- tartószerkezet", "nap", 375000, None, None),
    (64, "LED fal", "15 m² LED fal (P3.9)",
     "- P3.9-es LED fal elemekből\n- processzor, kábelezés\n- tartószerkezet", "nap", 720850, None, None),
    (65, "LED fal", "15 m² LED fal (P2.5)",
     "- P2.5-ös LED fal elemekből\n- processzor, kábelezés\n- tartószerkezet", "nap", 915850, None, None),
    (66, "LED fal", "18 m² LED fal beltéren (P4.8)", "", "nap", 450000, None, None),
    (67, "LED fal", "6–8 m² LED fal (P4.8)", "- vezérlő, üzemeltetési eszközök", "nap", 185000, 150000, 400000),
    (68, "LED fal", "4–5 m² LED fal (P4.8)", "", "nap", 125000, 35000, 150000),
    (69, "LED fal", "Szállítás, telepítés és bontás", "", "alkalom", 150000, 50000, 850000),
    (70, "LED fal", "Technikus, telepítés és bontás", "", "fo_nap", 60000, None, None),
    (71, "Utómunka", "Utómunka (vágás, fényelés, music license)", "", "project", 90000, 37500, 1250000),
    (72, "Utómunka", "Aftermovie / összefoglaló videó utómunkája",
     "- 2–3 perces videó\n- vágás, fényelés, music license", "db", 90000, 85000, 250000),
    (73, "Utómunka", "Social media videó utómunka (0–120 mp)",
     "- vágás, fényelés, music license\n- export 2 méretarányban", "db", 60000, None, None),
    (74, "Utómunka", "Social media videó utómunka (120–300 mp)", "- vágás, fényelés, music license",
     "db", 75000, None, None),
    (75, "Utómunka", "Short form content utómunka (reels/TikTok)", "", "db", 90000, 65000, 230000),
    (76, "Utómunka", "Mutáció / rövidítés elkészült videóból", "", "db", 45000, 15000, 60000),
    (77, "Utómunka", "Standup – 1 elkészült videó 2 méretarányban", "", "db", 60000, None, None),
    (78, "Utómunka", "Multicam vágás – teljes előadás",
     "- a teljes előadás felvételének multicam vágata\n- fényelés", "db", 100000, 100000, 120000),
    (79, "Utómunka", "Trailer videó utómunkája (60–90 mp)", "- vágás, fényelés, music license",
     "db", 90000, 85000, 100000),
    (80, "Utómunka", "Image / mood videó utómunkája", "- vágás, fényelés, music license", "db", 100000, 90000, 110000),
    (81, "Utómunka", "Werkfilm utómunkája", "- vágás, fényelés, music license", "db", 150000, 75000, 200000),
    (82, "Utómunka", "Interjú / riportvideó utómunkája", "- vágás, fényelés, logo- és feliratanimációk",
     "db", 90000, 45000, 140000),
    (83, "Utómunka", "Feliratozás", "", "db", 20000, 5000, 50000),
    (84, "Utómunka", "Grafikai elemek, animációk gyártása", "", "db", 150000, 150000, 250000),
    (85, "Utómunka", "Grafikai munka (óradíj)", "", "ora", 9500, None, None),
    (86, "Utómunka", "Hangutómunka", "", "project", 15000, 15000, 90000),
    (87, "Utómunka", "Music license", "", "db", 5000, 5000, 15000),
    (88, "Előkészítés", "Kreatív koncepció, scriptírás",
     "- koncepcióalkotás, egyeztetés\n- elfogadtatás, módosítási körök", "project", 200000, 150000, 555000),
    (89, "Előkészítés", "Prezentáció készítés", "", "db", 75000, None, None),
    (90, "Egyéb", "Gyártási költség", "humán- és technikai erőforrás járulékos költségei",
     "project", 60000, 10000, 150000),
    (91, "Egyéb", "Útiköltség", "Budapest belterületén kívülre történő kiszállás esetén (150 Ft/km)",
     "km", 150, None, None),
    (92, "Egyéb", "Szereplő, jogdíj", "", "fo", 100000, 25000, 300000),
    (93, "Egyéb", "Stáb catering", "", "alkalom", 250000, 250000, 1200000),
    (94, "Egyéb", "Kellékek", "- beszerzés, bérlés\n- berendezés, jelmez", "project", 350000, None, None),
    (95, "Egyéb", "Szoftver licenszek, technikai back-office", "", "project", 55000, 7500, 55000),
    (96, "Egyéb", "DJ szolgáltatás", "", "alkalom", 50000, None, None),
    (97, "Egyéb", "Social media csatornák menedzsmentje", "YouTube és TikTok csatornák", "honap", 250000, None, None),
    (98, "Egyéb", "Project management havidíj", "tartalmak koordinációja, felvételek szervezése",
     "honap", 300000, None, None),
]

#: Egymásra egy kattintással cserélhető tételek (a sor menüjében „Csere”).
VARIANSOK: dict[str, list[int]] = {
    "ledfal": [63, 64, 65, 66, 67, 68],
    "kameraszett": [31, 32, 33, 34],
    "fotos": [27, 28],
    "social-video": [73, 74],
    "dron": [41, 42],
}

MEGJEGYZES_NEV = "Standard HYPE megjegyzés"
#: A „Megjegyzés:” felirat az exportban külön kerül a szöveg elé.
MEGJEGYZES = (
    "A szolgáltatást csak írásos megrendelő esetén tudjuk megkezdeni.\n"
    "Megrendelő a megrendeléssel tudomásul veszi és elfogadja az alábbiakat:\n"
    "A technikai eszközöket az árajánlatban szereplő paraméterekkel a kért helyszínre és időpontban leszállítjuk, "
    "beüzemeljük az előzetes egyeztetés alapján (kamera pozíciók, áramigény, stúdióelhelyezés). Az eszközök spontán "
    "meghibásodásáért (túláram probléma, egyéb előre nem látható hiba előfordulás) a HYPE csapata NEM vállal "
    "felelősséget. Az ilyen jellegű problémákból eredő anyagi és erkölcsi kár a megrendelőt terheli. Ajánlatunkkal "
    "kapcsolatban készséggel állunk rendelkezésükre.\n"
    "Megrendelés lemondása: A megrendelő a beszerelés előtt 48 órán belüli lemondása esetén a szolgáltatási díj "
    "50%-át, 24 órán belüli lemondás esetén a teljes szolgáltatási díjat köteles kifizetni."
)

EMBER = "Emberi erőforrás"
ESZKOZ = "Eszközök"
UTOMUNKA = "Utómunka"
EGYEB = "Egyéb"
ELOKESZITES = "Előkészítés"


def s(tetel: int | None, alkalom: float = 1, menny: float = 1, *, opcio: bool = False, ar: int | None = None,
      nev: str | None = None, leiras: str | None = None, egyseg: str | None = None) -> dict:
    """Egy sablonsor: katalógus # (None: egyedi sor), alkalom × mennyiség."""
    return {"tetel": tetel, "alkalom": alkalom, "menny": menny, "opcio": opcio, "ar": ar,
            "nev": nev, "leiras": leiras, "egyseg": egyseg}


#: kulcs, név, leírás, árazás, összesítő címke, alkalom-felirat, tipikus végösszeg, szekciók
SABLONOK: list[dict] = [
    {
        "kulcs": "T1", "nev": "Rendezvény videó + fotó (aftermovie)",
        "leiras": "Eddig a leggyakoribb típus (150 ajánlat): operatőr, gimbal, mikroport, aftermovie; fotós és drón opcióként.",
        "mod": "one_off", "cimke": "A PROJECT TELJES KÖLTSÉGE", "tipikus": 700000,
        "szekciok": [
            (EMBER, [s(1), s(27, opcio=True), s(4, opcio=True)]),
            (ESZKOZ, [s(31), s(38), s(46), s(41, opcio=True)]),
            (UTOMUNKA, [s(72), s(73, 1, 2, opcio=True)]),
            (EGYEB, [s(90, ar=30000), s(91, 1, 0, opcio=True)]),
        ],
    },
    {
        "kulcs": "T2", "nev": "Image / reklám / kampányfilm",
        "leiras": "Koncepció, rendező, operatőr, fénypark és image-videó utómunka (49 ajánlat).",
        "mod": "one_off", "cimke": "A PROJECT TELJES KÖLTSÉGE", "tipikus": 600000,
        "szekciok": [
            (ELOKESZITES, [s(88)]),
            (EMBER, [s(6), s(1), s(13, opcio=True), s(22, opcio=True)]),
            (ESZKOZ, [s(31), s(32, opcio=True), s(38), s(39, opcio=True), s(44), s(48), s(46)]),
            (UTOMUNKA, [s(80), s(84, opcio=True), s(76, 1, 2, opcio=True)]),
            (EGYEB, [s(92, opcio=True), s(90, ar=80000), s(91, 1, 0, opcio=True)]),
        ],
    },
    {
        "kulcs": "T3", "nev": "Élő közvetítés / streaming (többkamerás)",
        "leiras": "Többkamerás közvetítés teljes stábbal és képkeverővel - a legnagyobb értékű típus (48 ajánlat).",
        "mod": "one_off", "cimke": "STREAMING SZOLGÁLTATÁS KÖLTSÉGE", "tipikus": 2000000,
        "szekciok": [
            (EMBER, [s(8), s(9), s(10), s(1, 1, 3), s(12), s(14), s(13), s(16, opcio=True), s(17, opcio=True)]),
            (ESZKOZ, [s(31, 1, 3), s(34, 1, 3, opcio=True), s(35, opcio=True), s(52), s(55), s(56),
                      s(54, opcio=True), s(40, opcio=True), s(58, opcio=True)]),
            (EGYEB, [s(90, ar=150000)]),
        ],
    },
    {
        "kulcs": "T3b", "nev": "1 kamerás stream (gyors)",
        "leiras": "Egy kamerás közvetítés csomagárral - pár kattintás.",
        "mod": "one_off", "cimke": "STREAMING SZOLGÁLTATÁS KÖLTSÉGE", "tipikus": None,
        "szekciok": [(None, [s(53), s(90, ar=100000)])],
    },
    {
        "kulcs": "T4", "nev": "Előadás / koncert felvétel (multicam)",
        "leiras": "Három kamerás előadás-rögzítés multicam vágással - főleg színházaknak (42 ajánlat).",
        "mod": "one_off", "cimke": "A PROJECT TELJES KÖLTSÉGE", "tipikus": 450000,
        "szekciok": [
            (EMBER, [s(1, 1, 3)]),
            (ESZKOZ, [s(31, 1, 3), s(38, opcio=True), s(48, leiras="kapott, kevert hang"), s(61, opcio=True)]),
            (UTOMUNKA, [s(78), s(79, opcio=True)]),
            (EGYEB, [s(90, ar=40000)]),
        ],
    },
    {
        "kulcs": "T5", "nev": "LED fal bérlés",
        "leiras": "15 m² LED fal szállítással, telepítéssel - a leggyorsabban növő típus. A P3.9 / P2.5 változat a sor menüjéből cserélhető.",
        "mod": "one_off", "cimke": "LED FAL BÉRLÉS KÖLTSÉGE", "alkalom_felirat": "Nap", "tipikus": 750000,
        "szekciok": [(None, [s(63), s(69), s(70, 1, 2), s(52, opcio=True), s(50, opcio=True), s(90, ar=50000),
                             s(91, 1, 0, opcio=True)])],
    },
    {
        "kulcs": "T6", "nev": "Fotózás (event / portré / társulati)",
        "leiras": "Fotós kidolgozott galériával; azonnali leadás, fény, retus, smink opcióként (33 ajánlat).",
        "mod": "one_off", "cimke": "A PROJECT TELJES KÖLTSÉGE", "tipikus": 250000,
        "szekciok": [(None, [s(27), s(28, opcio=True), s(30, opcio=True), s(29, opcio=True), s(22, opcio=True),
                             s(23, opcio=True), s(90, ar=20000), s(91, 1, 0, opcio=True)])],
    },
    {
        "kulcs": "T7", "nev": "Social media / short form tartalomgyártás",
        "leiras": "Koncepció, egynapos forgatás és 4 social videó (31 ajánlat).",
        "mod": "one_off", "cimke": "A PROJECT TELJES KÖLTSÉGE", "tipikus": 850000,
        "szekciok": [
            (ELOKESZITES, [s(88)]),
            (EMBER, [s(1), s(13), s(22, opcio=True)]),
            (ESZKOZ, [s(31), s(38), s(45), s(46)]),
            (UTOMUNKA, [s(73, 1, 4), s(77, opcio=True), s(83, 1, 4, opcio=True)]),
            (EGYEB, [s(92, opcio=True), s(90, ar=40000)]),
        ],
    },
    {
        "kulcs": "T8", "nev": "Konferencia / kurzus rögzítés",
        "leiras": "Két kamerás rögzítés hanggal és fénnyel; utómunka előadásonként (21 ajánlat).",
        "mod": "one_off", "cimke": "A PROJECT TELJES KÖLTSÉGE", "tipikus": 500000,
        "szekciok": [
            (EMBER, [s(1, 1, 2)]),
            (ESZKOZ, [s(31, 1, 2), s(39, opcio=True), s(44), s(46, 1, 2), s(48)]),
            (UTOMUNKA, [s(71, leiras="előadásonként állítható"), s(72, opcio=True)]),
            (EGYEB, [s(90, ar=40000)]),
        ],
    },
    {
        "kulcs": "T9", "nev": "Éves / havidíjas csomag",
        "leiras": "Keret-ajánlat havidíjjal (pl. 12 hónapra): project management, social media, kampányfilm, short form.",
        "mod": "monthly", "cimke": "A PROJECT TELJES KÖLTSÉGE", "tipikus": None,
        "szekciok": [(None, [
            s(88, nev="Kampánytervek / koncepció"),
            s(98, 1, 12),
            s(97, 1, 12, opcio=True),
            s(None, nev="Kampányfilm forgatási nap", leiras="- forgatási nap stábbal és technikával\n- az ár egyeztetendő",
              egyseg="nap", ar=0),
            s(75, 1, 12),
        ])],
    },
]
