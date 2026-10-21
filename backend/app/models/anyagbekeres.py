"""ANYAGBEKÉRŐ ÉS KREATÍV BRIEF (a felhasználó kérése).

A folyamat: a HYPE admin létrehoz egy anyagbekérést (Anyagbekeres) és elküldi
a megosztható linket az ügyfélnek/kollégának. A beküldő a linken megnyit egy
SAJÁT leadást (AnyagLeadas - saját, titkos folytatási tokennel), mappákba
rendezve feltölti a nyersanyagokat (AnyagMappa, AnyagFajl - közvetlen R2
multipart feltöltéssel), leírja, milyen videók készüljenek (VideoIgeny), és a
végén VÉGLEGESÍTI a leadást. Egy bekéréshez több, egymástól elzárt leadás
tartozhat - a beküldők egymás anyagait nem látják.

A fájlok a meglévő R2 tárolóba mennek (services/portal_storage.py), aláírt
URL-ekkel, az alkalmazásszerver memóriáján KÍVÜL - lásd
routes/anyagbekeres_public.py."""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Anyagbekeres(TimestampMixin, Base):
    """Egy anyagbekérés - az admin hozza létre, a link a beküldőké."""

    __tablename__ = "anyagbekeresek"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Rövid üdvözlőszöveg + feltöltési instrukciók a beküldői oldal tetejére.
    udvozlo_szoveg: Mapped[str | None] = mapped_column(Text)
    #: Meglévő projekthez kötés (nem kötelező) - törléskor a bekérés megmarad.
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    #: Ügyfélhez kötés VAGY szabad szöveges partnernév.
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"))
    partner_nev: Mapped[str | None] = mapped_column(String(255))
    #: Leadási határidő (UTC-naiv, a felület Budapest szerint mutatja).
    hatarido: Mapped[datetime | None] = mapped_column(DateTime)
    #: Belső felelős - ő kap értesítést a beérkező leadásokról.
    felelos_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    letrehozta_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))

    #: A megosztható link tokenje - visszavonható/újragenerálható (a régi link
    #: attól kezdve érvénytelen). NEM kitalálható (secrets.token_urlsafe).
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    #: Opcionális jelszó - a leadás megnyitásához kell, hash-elve tároljuk.
    jelszo_hash: Mapped[str | None] = mapped_column(String(255))
    #: A LINK lejárata (UTC-naiv) - lejárta után új feltöltés nem indítható,
    #: de az admin-oldali elérés és a meglévő anyagok megmaradnak.
    link_lejarat: Mapped[datetime | None] = mapped_column(DateTime)
    #: nyitott | lezart - a lezárt bekérésre új leadás/feltöltés nem megy.
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="nyitott")

    #: Kérünk-e videós briefet, vagy csak fájlleadást.
    kell_brief: Mapped[bool] = mapped_column(nullable=False, default=True)
    #: Feltöltési keret bájtban (None = a tároló általános keretein belül).
    meret_keret_bajt: Mapped[int | None] = mapped_column(BigInteger)
    #: Megengedett fájl-kiterjesztések vesszővel ("mp4,mov,wav") - üres = bármi.
    engedett_tipusok: Mapped[str | None] = mapped_column(String(500))
    #: Előre létrehozott mappák nevei - minden ÚJ leadás ezekkel indul.
    elore_mappak: Mapped[list | None] = mapped_column(JSON)

    leadasok: Mapped[list["AnyagLeadas"]] = relationship(
        back_populates="anyagbekeres", cascade="all, delete-orphan"
    )


class AnyagLeadas(TimestampMixin, Base):
    """Egy beküldő SAJÁT leadása - a saját, titkos folytatási tokenjével éri
    el; a közös bekérő-link önmagában nem ad hozzáférést hozzá."""

    __tablename__ = "anyag_leadasok"

    id: Mapped[int] = mapped_column(primary_key=True)
    anyagbekeres_id: Mapped[int] = mapped_column(
        ForeignKey("anyagbekeresek.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: A beküldő SAJÁT folytatási tokenje (piszkozat visszanyitásához).
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    bekuldo_nev: Mapped[str] = mapped_column(String(255), nullable=False)
    bekuldo_email: Mapped[str] = mapped_column(String(255), nullable=False)
    bekuldo_ceg: Mapped[str | None] = mapped_column(String(255))

    #: piszkozat | leadva | feldolgozas | kesz - a "leadva" a beküldő
    #: véglegesítésekor áll be; a feldolgozási állapotokat az admin kezeli.
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="piszkozat")
    leadva_at: Mapped[datetime | None] = mapped_column(DateTime)
    #: Feldolgozási felelős (admin állítja).
    felelos_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    #: BELSŐ megjegyzés - a beküldő számára soha nem elérhető.
    belso_megjegyzes: Mapped[str | None] = mapped_column(Text)

    anyagbekeres: Mapped["Anyagbekeres"] = relationship(back_populates="leadasok")
    mappak: Mapped[list["AnyagMappa"]] = relationship(back_populates="leadas", cascade="all, delete-orphan")
    fajlok: Mapped[list["AnyagFajl"]] = relationship(back_populates="leadas", cascade="all, delete-orphan")
    igenyek: Mapped[list["VideoIgeny"]] = relationship(
        back_populates="leadas", cascade="all, delete-orphan", order_by="VideoIgeny.sorrend"
    )


class AnyagMappa(TimestampMixin, Base):
    """Egy mappa a leadáson belül - a beküldő mappastruktúráját őrzi."""

    __tablename__ = "anyag_mappak"
    #: Ugyanabban a leadásban egy útvonal csak egyszer - a mappafeltöltés
    #: ugyanabba a mappába fűzi az azonos útvonalú fájlokat.
    __table_args__ = (UniqueConstraint("leadas_id", "utvonal", name="uq_anyag_mappa_utvonal"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    leadas_id: Mapped[int] = mapped_column(
        ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=False, index=True
    )
    szulo_id: Mapped[int | None] = mapped_column(ForeignKey("anyag_mappak.id", ondelete="CASCADE"))
    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    #: A TELJES relatív útvonal ("Nyersek/A kamera") - ebből áll vissza a fa,
    #: és a letöltött ZIP is ezt a struktúrát kapja.
    utvonal: Mapped[str] = mapped_column(String(1000), nullable=False)
    #: A beküldő rövid leírása/megjegyzése a mappához.
    leiras: Mapped[str | None] = mapped_column(Text)

    leadas: Mapped["AnyagLeadas"] = relationship(back_populates="mappak")


class AnyagFajl(TimestampMixin, Base):
    """Egy feltöltött fájl ÉS a feltöltési munkamenete (R2 multipart)."""

    __tablename__ = "anyag_fajlok"

    id: Mapped[int] = mapped_column(primary_key=True)
    leadas_id: Mapped[int] = mapped_column(
        ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mappa_id: Mapped[int | None] = mapped_column(ForeignKey("anyag_mappak.id", ondelete="SET NULL"), index=True)

    #: Az EREDETI fájlnév és a beküldő gépén volt relatív útvonal - a letöltés
    #: pontosan ezt a struktúrát állítja vissza.
    eredeti_nev: Mapped[str] = mapped_column(String(500), nullable=False)
    relativ_utvonal: Mapped[str | None] = mapped_column(String(1200))
    #: Az objektumtároló BELSŐ kulcsa (véletlen taggal - nem kitalálható).
    storage_key: Mapped[str] = mapped_column(String(600), nullable=False)
    meret_bajt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    content_type: Mapped[str | None] = mapped_column(String(255))

    #: feltoltes_alatt | kesz | hibas - a "kesz" CSAK a szerveroldali
    #: ellenőrzés (complete + head) után áll be.
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="feltoltes_alatt", index=True)
    #: R2 multipart azonosító + az eddig IGAZOLTAN feltöltött részek
    #: ({"1": "etag", ...}) - oldalfrissítés utáni folytatáshoz. A Cloudflare
    #: R2 UploadId-je hosszú base64-token (több száz karakter is lehet), ezért
    #: bőven méretezett - egy szűk mező itt "value too long" hibát adott.
    upload_id: Mapped[str | None] = mapped_column(String(1024))
    kesz_reszek: Mapped[dict | None] = mapped_column(JSON)
    kesz_at: Mapped[datetime | None] = mapped_column(DateTime)

    leadas: Mapped["AnyagLeadas"] = relationship(back_populates="fajlok")
    mappa: Mapped["AnyagMappa | None"] = relationship()


class VideoIgeny(TimestampMixin, Base):
    """Egy kért videó leírása (kreatív brief) - a leadás része."""

    __tablename__ = "video_igenyek"

    id: Mapped[int] = mapped_column(primary_key=True)
    leadas_id: Mapped[int] = mapped_column(
        ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sorrend: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    nev: Mapped[str] = mapped_column(String(255), nullable=False)
    #: "Mit szeretnél ebből az anyagból?" - a brief törzse.
    leiras: Mapped[str | None] = mapped_column(Text)
    hossz: Mapped[str | None] = mapped_column(String(120))
    #: Vesszővel: "Instagram,TikTok,weboldal" - szabad szöveg is belefér.
    felulet: Mapped[str | None] = mapped_column(String(255))
    keparany: Mapped[str | None] = mapped_column(String(30))
    hatarido: Mapped[datetime | None] = mapped_column(DateTime)
    #: "A teljes leadott anyagból" - ilyenkor nem kell forrás-hozzárendelés.
    teljes_anyagbol: Mapped[bool] = mapped_column(nullable=False, default=False)
    #: A "További részletek" mezők egyben (cél, stílus, kötelező jelenetek,
    #: feliratok, CTA, zene, referencialinkek, technikai elvárások, egyéb).
    reszletek: Mapped[dict | None] = mapped_column(JSON)
    #: Fájlhoz kötött, időkódos megjegyzések:
    #: [{"fajl_id": 12 | None, "szoveg": "00:01:12-00:01:45: ..."}].
    idokodok: Mapped[list | None] = mapped_column(JSON)

    leadas: Mapped["AnyagLeadas"] = relationship(back_populates="igenyek")
    forrasok: Mapped[list["VideoIgenyForras"]] = relationship(
        back_populates="igeny", cascade="all, delete-orphan"
    )


class VideoIgenyForras(Base):
    """Videóigény <-> forrásanyag kapcsolat (több-a-többhöz): egy igényhez
    több mappa/fájl, és egy mappa több igényhez is tartozhat - fájlmásolás
    nélkül. Vagy mappa_id, vagy fajl_id van kitöltve."""

    __tablename__ = "video_igeny_forrasok"
    __table_args__ = (
        UniqueConstraint("igeny_id", "mappa_id", name="uq_igeny_mappa"),
        UniqueConstraint("igeny_id", "fajl_id", name="uq_igeny_fajl"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    igeny_id: Mapped[int] = mapped_column(
        ForeignKey("video_igenyek.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mappa_id: Mapped[int | None] = mapped_column(ForeignKey("anyag_mappak.id", ondelete="CASCADE"), index=True)
    fajl_id: Mapped[int | None] = mapped_column(ForeignKey("anyag_fajlok.id", ondelete="CASCADE"), index=True)

    igeny: Mapped["VideoIgeny"] = relationship(back_populates="forrasok")


class AnyagEsemeny(Base):
    """Fontos állapotváltozások naplója (létrehozás, link-csere, lezárás,
    leadás-véglegesítés, feldolgozási állapot, export)."""

    __tablename__ = "anyag_esemenyek"

    id: Mapped[int] = mapped_column(primary_key=True)
    anyagbekeres_id: Mapped[int] = mapped_column(
        ForeignKey("anyagbekeresek.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leadas_id: Mapped[int | None] = mapped_column(ForeignKey("anyag_leadasok.id", ondelete="CASCADE"))
    tipus: Mapped[str] = mapped_column(String(50), nullable=False)
    adat: Mapped[dict | None] = mapped_column(JSON)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AnyagLeadasExport(Base):
    """Háttérben készülő ZIP egy leadásról (vagy egy mappájáról) - a meglévő
    portál-export mintája szerint (models/portal_export.py), lejáró letöltési
    linkkel. A job-ot egy háttérszál építi (lásd services/anyag_export.py)."""

    __tablename__ = "anyag_leadas_exportok"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    leadas_id: Mapped[int] = mapped_column(
        ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Ugyanarra a tartalomra nem épül két csomag (lásd portal_exports).
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    manifest: Mapped[list] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    filename: Mapped[str] = mapped_column(String(240), nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(500))
    object_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bytes_done: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    touched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
