"""Lara adatmodell (a modul magtáblái).

A modul minden adminisztrációs munkát egy tartós `admin_task` köré szervez;
minden javaslatnak van forrása, minden végrehajtásnak auditnyoma, minden
elakadásnak felelőse és oka. A HYPE OS EGYSZERVEZETES, ezért nincs `org_id`;
a hozzáférést a meglévő RBAC + rekordszintű szűkítés adja (lásd
docs/admin-agent/architecture.md). Pénzösszeget nem ebben a rétegben, hanem a
meglévő pénzügyi szolgáltatáson át (Expense, Numeric) tárolunk.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class SourceEvent(TimestampMixin, Base):
    """Egy bejövő forrásesemény (e-mail, feltöltött fájl, appon belüli trigger).

    Duplikáció-védelem: a (forras, forras_azonosito, forras_verzio) egyedi -
    ugyanaz az e-mail/dokumentum kétszer nem indít új feldolgozást. Egy
    eseményből 0..N admin_task keletkezhet."""

    __tablename__ = "aa_source_events"
    __table_args__ = (
        UniqueConstraint("forras", "forras_azonosito", "forras_verzio", name="uq_aa_source_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    #: gmail | upload | app | manual
    forras: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    #: A forrás stabil azonosítója (Gmail message id, fájl-hash, stb.).
    forras_azonosito: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    #: Változat (pl. Gmail historyId / új melléklet) - új verzió új feldolgozást
    #: indíthat, de a régit nem duplázza.
    forras_verzio: Mapped[str | None] = mapped_column(String(120))
    #: uj | feldolgozva | figyelmen_kivul | hibas
    allapot: Mapped[str] = mapped_column(String(30), nullable=False, default="uj", index=True)
    #: Nyers metaadat (feladó, tárgy, fájlnév, storage-kulcs) - a nagy tartalom
    #: a tárolóban, itt csak referencia + integritási hash.
    metaadat: Mapped[dict | None] = mapped_column(JSONB)
    tartalom_hash: Mapped[str | None] = mapped_column(String(64))
    feldolgozva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hiba: Mapped[str | None] = mapped_column(Text)


class AdminTask(TimestampMixin, Base):
    """Egy adminisztrációs munkaelem - Lara és az ember ugyanezt látja."""

    __tablename__ = "aa_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("aa_source_events.id", ondelete="SET NULL"), index=True
    )
    #: szamla | email | tig | szerzodes | egyeb (lásd enums.TaskType)
    tipus: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    altipus: Mapped[str | None] = mapped_column(String(60))
    cim: Mapped[str] = mapped_column(String(300), nullable=False)
    osszefoglalo: Mapped[str | None] = mapped_column(Text)
    #: lásd enums.TaskState
    allapot: Mapped[str] = mapped_column(String(30), nullable=False, default="new", index=True)
    prioritas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: R0..R3 (a legmagasabb tervezett művelet kockázata) - tájékoztató;
    #: a végrehajtási döntést a policy engine hozza.
    kockazat: Mapped[str | None] = mapped_column(String(4))
    #: 0 = alacsony, 1 = magas bizonytalanság; ISMERETLEN esetén NULL és emberi
    #: ellenőrzés (nem hamis nulla).
    uncertainty: Mapped[float | None] = mapped_column()
    #: A feladatra pillanatszerűen érvényes bizalmi szint (L0..L4).
    trust_level: Mapped[str] = mapped_column(String(4), nullable=False, default="L0")

    felelos_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    hatarido: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    project_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_codes.id", ondelete="SET NULL"), index=True
    )
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"))
    partner_nev: Mapped[str | None] = mapped_column(String(255))

    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("aa_tasks.id", ondelete="SET NULL"))
    blokkolo_ok: Mapped[str | None] = mapped_column(Text)
    utolso_hiba: Mapped[str | None] = mapped_column(Text)
    forras_referenciak: Mapped[dict | None] = mapped_column(JSONB)

    #: Optimista zárolás (a master prompt row_version-je).
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    befejezve_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(TimestampMixin, Base):
    """Egy Lara-futás egy taskhoz: terv, eszközök, modell/verzió, költség.

    NEM tárolunk rejtett modell-gondolatmenetet; ellenőrizhető döntési
    összefoglaló elegendő."""

    __tablename__ = "aa_agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("aa_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    #: modell/provider + verziók (config-, prompt-, policy-, tudás-verzió).
    modell: Mapped[str | None] = mapped_column(String(120))
    provider: Mapped[str | None] = mapped_column(String(60))
    verzio_info: Mapped[dict | None] = mapped_column(JSONB)
    #: Rövid, ellenőrizhető végrehajtási terv és forráshivatkozások.
    terv: Mapped[dict | None] = mapped_column(JSONB)
    kezdes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    veg_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_hasznalat: Mapped[int | None] = mapped_column(Integer)
    #: Becsült/mért költség a legkisebb pénzegységben (pl. mikro-USD), egész.
    koltseg_mikro: Mapped[int | None] = mapped_column(BigInteger)
    hibakod: Mapped[str | None] = mapped_column(String(80))


class ActionTrace(TimestampMixin, Base):
    """Audit-nyom: emberi VAGY Lara-művelet, minimális előtte/utána diffel."""

    __tablename__ = "aa_action_traces"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("aa_tasks.id", ondelete="SET NULL"), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("aa_agent_runs.id", ondelete="SET NULL"))
    #: human | agent | system
    szereplo: Mapped[str] = mapped_column(String(10), nullable=False)
    szereplo_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    muvelet: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Érintett rekord típusa+azonosítója (pl. "expense:1234").
    eroforras: Mapped[str | None] = mapped_column(String(120), index=True)
    diff: Mapped[dict | None] = mapped_column(JSONB)
    eredmeny: Mapped[str | None] = mapped_column(String(40))
    tortent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class Correction(TimestampMixin, Base):
    """Emberi javítás Lara javaslatán - a tanulás legerősebb jele.

    A későbbi emberi változtatás nem feltétlenül korrekció (lehet új üzleti
    adat); a `tipus` (enums.CorrectionType) különbözteti meg, kétes esetben
    'besorolando'."""

    __tablename__ = "aa_corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("aa_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    proposal_id: Mapped[int | None] = mapped_column(ForeignKey("aa_action_proposals.id", ondelete="SET NULL"))
    eredeti: Mapped[dict | None] = mapped_column(JSONB)
    javitott: Mapped[dict | None] = mapped_column(JSONB)
    mezo_diff: Mapped[dict | None] = mapped_column(JSONB)
    javito_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    magyarazat: Mapped[str | None] = mapped_column(Text)
    tipus: Mapped[str] = mapped_column(String(30), nullable=False, default="besorolando")
    #: uj | feldolgozva (az éjszakai distill dolgozza fel, kurzorral)
    feldolgozas_allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="uj", index=True)


class ActionProposal(TimestampMixin, Base):
    """Konkrét eszköz + validált paraméterek: immutable payload + hash + lejárat.

    A jóváhagyás EHHEZ a hash-hez kötődik; bármely lényeges változás
    érvényteleníti."""

    __tablename__ = "aa_action_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("aa_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("aa_agent_runs.id", ondelete="SET NULL"))
    #: A hívandó, regisztrált eszköz neve (lásd tool-registry).
    eszkoz: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Az immutable payload (validált paraméterek) + a célerőforrás-verziók.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cel_verziok: Mapped[dict | None] = mapped_column(JSONB)
    #: A payload determinista hash-e (a jóváhagyás ehhez kötődik).
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: SZERVEROLDALI kockázati besorolás (R0..R3).
    kockazat: Mapped[str] = mapped_column(String(4), nullable=False)
    ellenorzesek: Mapped[dict | None] = mapped_column(JSONB)
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="ready", index=True)
    lejar_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Approval(TimestampMixin, Base):
    """Egy javaslat-verzió/hash emberi jóváhagyása - EGY végrehajtásra."""

    __tablename__ = "aa_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("aa_action_proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Amit jóváhagytak - a proposal payload-hash-e a döntés pillanatában.
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    donto_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    indok: Mapped[str | None] = mapped_column(Text)
    dontes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lejar_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Egy jóváhagyás egyszer használható fel (consumed a végrehajtáskor).
    felhasznalt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionExecution(TimestampMixin, Base):
    """Egy tényleges eszköz-végrehajtás: idempotenciakulcs + állapot + egyeztetés."""

    __tablename__ = "aa_action_executions"
    __table_args__ = (
        UniqueConstraint("idempotencia_kulcs", name="uq_aa_execution_idempotencia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("aa_action_proposals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approval_id: Mapped[int | None] = mapped_column(ForeignKey("aa_approvals.id", ondelete="SET NULL"))
    #: Dupla kattintás / két worker mellett is EGY végrehajtási rekord.
    idempotencia_kulcs: Mapped[str] = mapped_column(String(120), nullable=False)
    allapot: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    probalkozasok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kulso_azonosito: Mapped[str | None] = mapped_column(String(255))
    eredmeny: Mapped[dict | None] = mapped_column(JSONB)
    egyeztetes_allapot: Mapped[str | None] = mapped_column(String(30))
    #: Fencing token: lejárt lease-ű worker ne kezdhessen új mellékhatást.
    fencing_token: Mapped[int | None] = mapped_column(BigInteger)


class PlaybookRule(TimestampMixin, Base):
    """Explicit SOP / preferencia. A gépi javaslat elkülönül az aktív szabálytól."""

    __tablename__ = "aa_playbook_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    hatokor: Mapped[str] = mapped_column(String(60), nullable=False, index=True)  # pl. "szamla", "email:beérkezés"
    cim: Mapped[str] = mapped_column(String(200), nullable=False)
    feltetelek: Mapped[dict | None] = mapped_column(JSONB)
    tartalom: Mapped[str] = mapped_column(Text, nullable=False)
    prioritas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verzio: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: draft | pending | active | retired (enums.RuleState)
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    forras_esetek: Mapped[dict | None] = mapped_column(JSONB)
    johaggyo_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    ervenyes_ig: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrustPolicy(TimestampMixin, Base):
    """Bizalmi szint feladattípus×altípus szinten. A modell nem módosíthatja."""

    __tablename__ = "aa_trust_policies"
    __table_args__ = (UniqueConstraint("tipus", "altipus", name="uq_aa_trust_tipus_altipus"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tipus: Mapped[str] = mapped_column(String(30), nullable=False)
    altipus: Mapped[str | None] = mapped_column(String(60))
    #: L0..L4 (alap L0).
    szint: Mapped[str] = mapped_column(String(4), nullable=False, default="L0")
    #: L3+ mellett auto-ra engedélyezett R2 altípusok (alap: üres lista).
    auto_engedett_altipusok: Mapped[list | None] = mapped_column(JSONB)
    modositotta_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))


class AdminAgentSetting(TimestampMixin, Base):
    """A modul globális kapcsolói - EGY sor (singleton, id=1).

    Biztonságos alapállás: modul kikapcsolva, mellékhatás tiltva, vészleállítás
    nem aktív (de a modul-ki és a mellékhatás-tiltás miatt így sem fut semmi)."""

    __tablename__ = "aa_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    side_effects_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Globális vészleállítás (minden mellékhatásos lépés előtt ellenőrizve).
    kill_switch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kill_switch_indok: Mapped[str | None] = mapped_column(Text)
    #: Engedélyezett ingest-források (pl. {"gmail": {"cimkek": [...]}}), alap üres.
    engedett_forrasok: Mapped[dict | None] = mapped_column(JSONB)
    #: Futás-/költséglimitek (tervezési lépés, eszközhívás, token, költség).
    limitek: Mapped[dict | None] = mapped_column(JSONB)
    modositotta_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))


# ── F fázis: memória, tanulás, értékelés, verziózott kiadások ────────────────


class MemoryChunk(TimestampMixin, Base):
    """Visszakereshető tudás-darab (tisztított tartalom + forrás). A pgvector
    OPCIONÁLIS: ha nincs telepítve, az `embedding` üres marad, és a keresés
    pontos/szöveges fallbackre vált (lásd admin_agent/memory.py). Csak a
    JÓVÁHAGYOTT tanulási halmazból származó, érvényes, nem visszavont darab
    használható éles döntésben."""

    __tablename__ = "aa_memory_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    hatokor: Mapped[str] = mapped_column(String(60), nullable=False, index=True)  # pl. "szamla", "email"
    tartalom: Mapped[str] = mapped_column(Text, nullable=False)
    forras: Mapped[str | None] = mapped_column(String(120))
    forras_verzio: Mapped[str | None] = mapped_column(String(120))
    minosites: Mapped[str] = mapped_column(String(20), nullable=False, default="jovahagyott")
    #: A tanulási halmaz: "jovahagyott" (retrievalhez), "holdout" SOHA nem ide kerül.
    tanulasi_halmaz: Mapped[str] = mapped_column(String(20), nullable=False, default="jovahagyott", index=True)
    embedding: Mapped[list | None] = mapped_column(JSONB)  # pgvector hiányában JSON-lista vagy None
    embedding_modell: Mapped[str | None] = mapped_column(String(120))
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    ervenyes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    visszavont: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: A forrásrekord (TIG/szerződés/kiadás) keletkezése — megfigyelt példánál.
    forras_keletkezes: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: A tanulás kezdete ELŐTTI vagy Notionből importált rekordból származik
    #: (lásd admin_agent/observer.py `korszak_rendezes`). Ilyenből nem lesz új
    #: jelölt; a már jóváhagyott csak az újak után, kisebb súllyal kerül elő.
    regi_korszak: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class EvalCase(TimestampMixin, Base):
    """Értékelő eset (holdout vagy szintetikus). A holdout-válaszok NEM
    elérhetők a distill/retrieval számára; visszajátszáskor a döntés
    időpontjában ismert adatpillanatképet (`bemenet`) használjuk."""

    __tablename__ = "aa_eval_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(200), nullable=False)
    tipus: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    altipus: Mapped[str | None] = mapped_column(String(60))
    #: A döntés időpontjában ismert bemenet (pl. beérkező számla kinyert mezői).
    bemenet: Mapped[dict] = mapped_column(JSONB, nullable=False)
    #: Elvárt kimenet/invariáns (pl. {"cel_tipus": "mukodesi"} vagy {"blokkolt": true}).
    elvart: Mapped[dict | None] = mapped_column(JSONB)
    #: "holdout" (valós, anonimizált) vagy "szintetikus".
    halmaz: Mapped[str] = mapped_column(String(20), nullable=False, default="szintetikus", index=True)
    forras: Mapped[str | None] = mapped_column(String(120))
    ervenyes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EvalRun(TimestampMixin, Base):
    """Egy értékelő futás eredménye. Sikertelen futás (kritikus hiba vagy
    küszöb alatti arány) NEM aktiválhat kiadást."""

    __tablename__ = "aa_eval_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    release_id: Mapped[int | None] = mapped_column(ForeignKey("aa_agent_releases.id", ondelete="SET NULL"))
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="futott")
    osszes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sikeres: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kritikus_hiba: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    atment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    eredmeny: Mapped[dict | None] = mapped_column(JSONB)  # esetenkénti részletek
    kezdes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    veg_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LearningRun(TimestampMixin, Base):
    """Egy háttér-tanuló (distill) futás. A `kurzor` a legutóbb feldolgozott
    korrekció után áll — újraindításkor nem dolgozza fel kétszer ugyanazt."""

    __tablename__ = "aa_learning_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="futott")
    feldolgozott_korrekciok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uj_szabaly_jeloltek: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uj_pelda_jeloltek: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sop_keresek: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kurzor: Mapped[str | None] = mapped_column(String(60))
    osszefoglalo: Mapped[dict | None] = mapped_column(JSONB)
    kezdes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    veg_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRelease(TimestampMixin, Base):
    """Verziózott tudás-/konfigurációkiadás. A jelölt NEM aktiválhatja magát;
    aktiválás csak sikeres eval után, jogosult ember által."""

    __tablename__ = "aa_agent_releases"

    id: Mapped[int] = mapped_column(primary_key=True)
    verzio: Mapped[str] = mapped_column(String(40), nullable=False)
    #: Mi változott: "rules" / "prompt" / "policy" / "model" / "retrieval".
    tipus: Mapped[str] = mapped_column(String(20), nullable=False, default="rules")
    leiras: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict | None] = mapped_column(JSONB)  # rögzített verziók/pinnek
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="jelolt", index=True)
    eval_run_id: Mapped[int | None] = mapped_column(ForeignKey("aa_eval_runs.id", ondelete="SET NULL"))
    aktivalta_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    aktivalva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Outbox(TimestampMixin, Base):
    """Tranzakciós outbox: a belső állapotváltozás és a feldolgozási/értesítési
    esemény egy tranzakcióban íródik; a kézbesítő külön, idempotensen dolgozza
    fel. Korlátos retry + karantén."""

    __tablename__ = "aa_outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    esemeny_tipus: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    probalkozasok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kovetkezo_probalkozas_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kulso_azonosito: Mapped[str | None] = mapped_column(String(255))
    hiba: Mapped[str | None] = mapped_column(Text)
    feldolgozva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LaraKerdes(TimestampMixin, Base):
    """Lara kérdése: az önellenőrzés során talált, számára MEGMAGYARÁZATLAN
    eltérés (amit javasolt volna ≠ amit az ember rögzített). A válasz tudássá
    válik (lásd admin_agent/onellenorzes.py). Partnerenként és végső céltípusonként
    egy nyitott kérdés gyűjti az érintett eseteket (`kulcs`)."""

    __tablename__ = "aa_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipus: Mapped[str] = mapped_column(String(40), nullable=False, default="szamla_besorolas")
    #: nyitott | megvalaszolt | elvetve
    allapot: Mapped[str] = mapped_column(String(20), nullable=False, default="nyitott", index=True)
    #: Csoportosító kulcs: "<partner_kulcs>|<végső céltípus>".
    kulcs: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    partner_nev: Mapped[str | None] = mapped_column(String(300))
    kerdes: Mapped[str] = mapped_column(Text, nullable=False)
    #: {"esetek": [...], "lara_javaslata": {...}, "valosag": {...}, "alap": ...}
    kontextus: Mapped[dict | None] = mapped_column(JSONB)
    #: mindig | kivetel | magyarazat | hibas | elvet
    valasz_tipus: Mapped[str | None] = mapped_column(String(20))
    valasz_szoveg: Mapped[str | None] = mapped_column(Text)
    megvalaszolta_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    megvalaszolva_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    szabaly_id: Mapped[int | None] = mapped_column(ForeignKey("aa_playbook_rules.id", ondelete="SET NULL"))
