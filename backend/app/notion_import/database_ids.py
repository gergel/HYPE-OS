"""A HYPE Notion workspace adatbázis-ID-i, a scripts/notion_discover.py 2026-07-02-i
futtatásának kimenetéből rögzítve. Ha új adatbázis kerül be vagy egy ID megváltozik,
futtasd újra a discovery scriptet és frissítsd itt.

A docs/hype_os_migration_map.md-ban "Törlődik, adatmigráció nélkül" jelölésű táblákat
(4 névre szabott elszámolás-klón, 2025 CEU RecruiTECH Blue, 2025 beosztása, New form)
és az audit-jellegű, nálunk önálló entitásként nem létező táblákat (Leltárak, Leltár
tételek) szándékosan nem importáljuk - lásd a scripts/notion_import.py végén a
SKIPPED_DATABASES listát a pontos indoklással.
"""

MEGRENDELOI_KONTAKTOK = "1e7c9afd-d53b-800c-9818-dfd0389d061d"
KULSOS_ES_BELSOS = "e23876f7-f17b-4fcb-ac63-52b63303c7c8"
VAGOK = "1fcc9afd-d53b-8094-8663-de3af2f442c3"
ORABER_NAPIBER = "2bcc9afd-d53b-8027-a5eb-c55c4cde2765"
LELTAR = "f49c2844-eb7f-4879-8f59-8384b24694f1"
KAMPANYOK = "1f9c9afd-d53b-809b-8185-f691d01aaf2e"
TEENDOK = "2d7c9afd-d53b-80b6-82a8-de2f721240e0"
AGI_TODO_LIST = "383c9afd-d53b-80ce-8a32-dcf2a298e7b9"
HYPE_TODO_LIST = "356c9afd-d53b-80be-98a5-c041be870307"
ARCHIVE_FELADATOK = "d1e517d5-d92a-471d-9804-6795d76f85b1"
KERETSZERZODES = "20dc9afd-d53b-8023-a510-e1f70949e9b7"
ALVALLALKOZO_KERETSZERZODES = "218c9afd-d53b-8080-a094-eff698c1fd89"
HYPE_ADMIN_PROJEKTKODOK = "20dc9afd-d53b-803e-a6c0-d89c6e2f8c2f"
# A külsősök PROJEKTENKÉNTI papírjai: soronként egy (ember, forgatás) pár, rajta
# az eseti szerződés és a TIG állapota/összege/fájljai. A 2026-07-02-i felmérés
# csak annyit rögzített róla, hogy nem munkatárs-nyilvántartó tábla, ezért
# kimaradt az importból - emiatt a rendszer nem tudott a Notionban már elkészült
# papírokról (lásd importers_kulsos.py).
KULSOS = "20ec9afd-d53b-80d9-a78f-feeb05492d22"

# Fázis 2, 2. kör (Main Database-re épül, később következik):
MAIN_DATABASE = "4ab04fc0-a826-42b6-bd01-354ae11ea291"
UTOMUNKA = "1f8c9afd-d53b-8019-92e5-dbf08dbc4957"
TIMESHEET_PUBLIC = "1e7c9afd-d53b-809b-bbe3-d6aafae6fdc6"
TIMESHEET_PRIVATE = "2bec9afd-d53b-80f3-8228-ceb8ef3be35d"
KIADASOK = "218c9afd-d53b-804f-8ffe-c0a4307dbfa3"
PROJEKT_KIADASOK = "23cc9afd-d53b-809b-a33d-eb687bf6acd5"
BELSOS_EXTRA_KIADASOK = "240c9afd-d53b-808e-ba1b-e4230add850b"
BEVETELEK = "218c9afd-d53b-80d9-b2f4-f583ce991885"
KP_FORGALOM = "2bec9afd-d53b-80a5-bdff-e00fb187d4ca"
VISSZAJELZESSEK = "c20b3377-db65-436e-92a7-76571fc58169"

# Nem importáljuk (a felhasználó explicit döntése, 2026-07-02: "csak tesztek voltak,
# nincs szükség rájuk") - a konstansok itt maradnak referenciaként, ha mégis kellenének:
OPERATORI_DISZPO = "149c9afd-d53b-8096-bccf-d6f43093c4d7"
ESZKOZKIVITEL = "240c9afd-d53b-80ee-bd9a-f9eb34e91dea"

# A belsősök havi TIG-jei. A 2026-07-02-i discovery futtatáskor ez a tábla nem
# volt megosztva az integrációval, ezért nincs ID-ja: az importer NÉV szerint
# keresi meg (lásd importers_belsos.belsos_tig_database_id). Ha egyszer
# lefuttatod a discoveryt és megvan az ID, írd ide - onnantól nem kell keresni.
BELSOS_TIG = ""

# Fázis 2, 3. kör (egyedi logikájú maradék táblák):
STOCK_IGENYEK = "2edc9afd-d53b-8087-bf72-edd6027147ef"
GERI_ELSZAMOLAS = "301c9afd-d53b-80f7-be78-f43bdc3f0486"
TOROLT_ANYAGOK = "223c9afd-d53b-80bf-ac08-e99816340f48"
